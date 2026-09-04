"""
core/state.py
Shared agent state — a single source of truth passed between all agents.
Holds account snapshot, open positions, daily P&L, and signal cache.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Any


@dataclass
class OptionPosition:
    """Represents a single options leg position."""
    symbol: str            # OCC symbol e.g. SPY240119C00450000
    underlying: str        # e.g. SPY
    strategy: str          # iron_condor | credit_spread | protective_put
    side: str              # buy | sell
    qty: int
    avg_entry_price: float
    current_price: float = 0.0
    delta: float = 0.0
    theta: float = 0.0
    unrealized_pnl: float = 0.0
    stop_loss_price: float = 0.0   # Calculated at entry
    group_id: str = ""             # Ties legs of the same strategy together


@dataclass
class SignalSnapshot:
    """Market signals for a single underlying at a point in time."""
    symbol: str
    price: float
    rsi: float
    iv_rank: float         # 0–100 percentile of current IV vs 52-week range
    current_iv: float      # Current IV (annualized %)
    iv_52w_high: float
    iv_52w_low: float
    trend: str             # "bullish" | "bearish" | "neutral"
    recommended_strategy: str = ""
    reasoning: str = ""


@dataclass
class AgentState:
    """
    Central shared state threaded through all agents each cycle.
    Uses an asyncio Lock to guard writes from concurrent agent updates.
    """
    # Account
    equity: float = 100_000.0
    buying_power: float = 100_000.0
    daily_pnl: float = 0.0
    starting_balance: float = 100_000.0
    session_date: date = field(default_factory=date.today)

    # Positions — keyed by OCC symbol
    positions: Dict[str, OptionPosition] = field(default_factory=dict)

    # Signals — keyed by underlying symbol
    signals: Dict[str, SignalSnapshot] = field(default_factory=dict)

    # Risk flags
    trading_halted: bool = False
    halt_reason: str = ""

    # Execution history (last N orders for dashboard)
    order_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Time-series history for the live Equity Chart
    equity_history: List[Dict[str, Any]] = field(default_factory=list)

    # Recent agent activity logs for the dashboard
    recent_logs: List[str] = field(default_factory=list)

    # Internal lock — not serialized
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    async def add_log(self, message: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        async with self._lock:
            self.recent_logs.append(f"[{timestamp}] {message}")
            if len(self.recent_logs) > 8:  # Keep last 8 logs for the UI
                self.recent_logs.pop(0)

    async def update_account(self, equity: float, buying_power: float):
        import datetime
        async with self._lock:
            # Reset daily P&L on new session date
            today = date.today()
            if today != self.session_date:
                self.daily_pnl = 0.0
                self.session_date = today
            self.daily_pnl = equity - self.starting_balance
            self.equity = equity
            self.buying_power = buying_power

            # Append to history for the live chart (limit to 100 points)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            if not self.equity_history or self.equity_history[-1]["equity"] != equity:
                self.equity_history.append({"time": ts, "equity": equity})
                if len(self.equity_history) > 100:
                    self.equity_history.pop(0)

    async def add_position(self, pos: OptionPosition):
        async with self._lock:
            self.positions[pos.symbol] = pos

    async def remove_position(self, symbol: str):
        async with self._lock:
            self.positions.pop(symbol, None)

    async def update_signal(self, sig: SignalSnapshot):
        async with self._lock:
            self.signals[sig.symbol] = sig

    async def halt_trading(self, reason: str):
        async with self._lock:
            self.trading_halted = True
            self.halt_reason = reason

    async def log_order(self, order_info: Dict[str, Any]):
        async with self._lock:
            self.order_log.append(order_info)
            # Keep only the last 50 orders in memory
            if len(self.order_log) > 50:
                self.order_log = self.order_log[-50:]

    @property
    def portfolio_delta(self) -> float:
        """Sum of all position deltas — proxy for directional exposure."""
        return sum(p.delta * p.qty * (1 if p.side == "buy" else -1)
                   for p in self.positions.values())

    @property
    def portfolio_theta(self) -> float:
        """Sum of all position thetas — proxy for daily time decay P&L."""
        return sum(p.theta * p.qty * (1 if p.side == "buy" else -1)
                   for p in self.positions.values())

    @property
    def open_position_count(self) -> int:
        return len(self.positions)
