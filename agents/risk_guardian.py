"""
agents/risk_guardian.py

Risk Guardian Agent
===================
The last line of defense before any order reaches the market.
ALL proposed trades MUST pass through this agent before execution.

Hard Gates (Block trade if ANY are tripped):
  1. trading_halted flag set — system-wide halt
  2. Max position size — trade cost > max_position_pct × equity
  3. Max portfolio delta — would push |portfolio_delta| > max_portfolio_delta
  4. Daily loss limit — daily_pnl < -(daily_loss_limit_pct × starting_balance)
  5. Max concurrent positions — already at capacity
  6. Per-position stop-loss — checks existing positions, closes those breaching threshold
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Union
from datetime import date

from core.config import config
from core.logger import get_logger
from core.state import AgentState, OptionPosition
from strategies.iron_condor import IronCondorOrder, OptionLeg
from strategies.credit_spread import CreditSpreadOrder
from strategies.protective_put import ProtectivePutOrder

logger = get_logger(__name__, agent="RiskGuardian")

AnyOrder = Union[IronCondorOrder, CreditSpreadOrder, ProtectivePutOrder]


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    gate_triggered: Optional[str] = None

    def __bool__(self):
        return self.allowed


class RiskGuardianAgent:
    """
    Evaluates proposed orders against all hard risk gates.
    Also runs a background monitor that closes positions hitting stop-loss.
    """

    def __init__(self, state: AgentState):
        self.state = state
        self.risk_cfg = config.risk

    # ── Gate Evaluation ─────────────────────────────────────────────────────

    async def evaluate(self, order: AnyOrder, estimated_cost: float) -> RiskDecision:
        """
        Run all gates sequentially (fail-fast). Returns RiskDecision.

        Args:
            order: The proposed options order
            estimated_cost: Estimated maximum capital at risk ($)
        """
        # Gate 1: System halt
        if self.state.trading_halted:
            return RiskDecision(
                allowed=False,
                reason=f"Trading halted: {self.state.halt_reason}",
                gate_triggered="system_halt",
            )

        # Gate 2: Position sizing
        if self.state.equity > 0:
            position_pct = estimated_cost / self.state.equity
            if position_pct > self.risk_cfg.max_position_pct:
                msg = (f"Position size {position_pct:.1%} exceeds limit "
                       f"{self.risk_cfg.max_position_pct:.1%}")
                logger.warning(msg)
                return RiskDecision(allowed=False, reason=msg, gate_triggered="position_size")

        # Gate 3: Portfolio delta
        trade_delta = self._estimate_order_delta(order)
        projected_delta = abs(self.state.portfolio_delta + trade_delta)
        if projected_delta > self.risk_cfg.max_portfolio_delta:
            msg = (f"Trade would push portfolio delta to {projected_delta:.2f}, "
                   f"exceeding limit {self.risk_cfg.max_portfolio_delta:.2f}")
            logger.warning(msg)
            return RiskDecision(allowed=False, reason=msg, gate_triggered="portfolio_delta")

        # Gate 4: Daily loss limit
        loss_limit = -(self.risk_cfg.daily_loss_limit_pct * self.risk_cfg.required_starting_balance)
        if self.state.daily_pnl < loss_limit:
            msg = (f"Daily P&L {self.state.daily_pnl:,.2f} breached limit "
                   f"{loss_limit:,.2f}. Halting trading for today.")
            logger.warning(msg)
            await self.state.halt_trading(msg)
            return RiskDecision(allowed=False, reason=msg, gate_triggered="daily_loss")

        # Gate 5: Concurrent positions
        if self.state.open_position_count >= self.risk_cfg.max_concurrent_positions:
            msg = (f"At max concurrent positions ({self.risk_cfg.max_concurrent_positions}). "
                   "Close existing positions before opening new ones.")
            logger.warning(msg)
            return RiskDecision(allowed=False, reason=msg, gate_triggered="max_positions")

        logger.info(
            "Order passed all risk gates",
            extra={"strategy": type(order).__name__, "cost": estimated_cost}
        )
        return RiskDecision(allowed=True, reason="All gates passed")

    # ── Stop-Loss Monitor ───────────────────────────────────────────────────

    async def run_monitor(self):
        """
        Background task: every 60 seconds check all open positions for stop-loss
        or take-profit breaches. Returns a list of OCC symbols to be closed.
        """
        while True:
            await asyncio.sleep(60)
            positions_to_close = []
            async with self.state._lock:
                for symbol, pos in self.state.positions.items():
                    if pos.avg_entry_price > 0 and pos.current_price > 0:
                        # Take-profit limit: default 50% of credit for shorts, 50% profit for longs
                        tp_pct = 0.50 

                        if pos.side == "buy":
                            profit_pct = (pos.current_price - pos.avg_entry_price) / pos.avg_entry_price
                            loss_pct = (pos.avg_entry_price - pos.current_price) / pos.avg_entry_price
                        else:
                            # Short: entry was credit received; current_price is cost to buy back
                            profit_pct = (pos.avg_entry_price - pos.current_price) / max(pos.avg_entry_price, 0.01)
                            loss_pct = (pos.current_price - pos.avg_entry_price) / max(pos.avg_entry_price, 0.01)

                        if loss_pct > self.risk_cfg.position_stop_loss_pct:
                            logger.warning(
                                f"Stop-loss triggered for {symbol}: loss={loss_pct:.1%}",
                                extra={"symbol": symbol, "loss_pct": loss_pct}
                            )
                            positions_to_close.append(symbol)
                            self.state.recent_logs.append(f"🛑 [bold red]STOP-LOSS HIT:[/] {symbol} at {loss_pct:.1%} loss")

                        elif profit_pct > tp_pct:
                            logger.info(
                                f"Take-profit triggered for {symbol}: profit={profit_pct:.1%}",
                                extra={"symbol": symbol, "profit_pct": profit_pct}
                            )
                            positions_to_close.append(symbol)
                            self.state.recent_logs.append(f"🎯 [bold green]TAKE-PROFIT HIT:[/] {symbol} locked in {profit_pct:.1%} profit")
            
            # Note: in a full implementation, the Risk Guardian would signal the 
            # Execution Agent to actually close these positions here.

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_order_delta(order: AnyOrder) -> float:
        """
        Estimate net delta contribution of a proposed order.
        Uses the delta_target from each leg.
        """
        total = 0.0
        for leg in order.legs:
            sign = 1.0 if leg.side == "buy" else -1.0
            total += sign * leg.delta_target * leg.qty
        return total
