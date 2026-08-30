"""
agents/strategy_selector.py

Strategy Selector Agent
=======================
Reads the SignalSnapshot from AgentState and selects the right
options strategy + target symbol for this cycle.

Decision priority:
  1. If Gemini LLM is enabled → ask Gemini for a reasoned decision
  2. Fallback → pure rule-based logic from signal recommendations

Output: A structured StrategyProposal ready for the Risk Guardian.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Union

from core.config import config
from core.logger import get_logger
from core.state import AgentState, SignalSnapshot
from strategies.iron_condor import IronCondorOrder, build_iron_condor
from strategies.credit_spread import CreditSpreadOrder, build_bull_put_spread, build_bear_call_spread
from strategies.protective_put import ProtectivePutOrder, build_protective_put

logger = get_logger(__name__, agent="StrategySelector")

AnyOrder = Union[IronCondorOrder, CreditSpreadOrder, ProtectivePutOrder]

# ── Optional Gemini imports ──────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


@dataclass
class StrategyProposal:
    """The output of the Strategy Selector — a fully constructed order + cost estimate."""
    order: AnyOrder
    estimated_cost: float    # Max capital at risk for risk gate evaluation
    signal: SignalSnapshot
    rationale: str           # LLM or rule-based explanation logged for audit


class StrategySelectorAgent:
    """
    Analyzes all fresh SignalSnapshots and produces one StrategyProposal
    per eligible underlying (if risk gates permit).
    """

    def __init__(self, state: AgentState):
        self.state = state
        self.gemini_client = None
        if GEMINI_AVAILABLE and config.gemini.enabled:
            self.gemini_client = genai.Client(api_key=config.gemini.api_key)
            logger.info(f"Gemini LLM enabled: model={config.gemini.model}")
        else:
            logger.info("Running in rule-based mode (no Gemini API key set)")

    # ── Main Selection Loop ─────────────────────────────────────────────────

    async def select_best_opportunity(self) -> Optional[StrategyProposal]:
        """
        Evaluate all signals and return the single best StrategyProposal.
        Returns None if no valid opportunity found or no fresh signals.
        """
        if not self.state.signals:
            logger.info("No signals available yet — waiting for scanner")
            return None

        best: Optional[StrategyProposal] = None
        best_score = -1.0

        for symbol, signal in self.state.signals.items():
            if signal.recommended_strategy == "no_trade":
                continue

            proposal = await self._evaluate_signal(signal)
            if proposal is None:
                continue

            score = self._score_proposal(proposal)
            if score > best_score:
                best_score = score
                best = proposal

        if best:
            logger.info(
                f"Best opportunity: {best.signal.symbol} → {type(best.order).__name__}",
                extra={"score": round(best_score, 2), "rationale": best.rationale}
            )
        else:
            logger.info("No actionable opportunities found this cycle")

        return best

    # ── Per-Symbol Evaluation ───────────────────────────────────────────────

    async def _evaluate_signal(self, signal: SignalSnapshot) -> Optional[StrategyProposal]:
        """Ask the LLM (or rule engine) for a decision, then build the order."""
        if self.gemini_client:
            strategy_name, rationale = await self._ask_gemini(signal)
        else:
            strategy_name = signal.recommended_strategy
            rationale = self._rule_rationale(signal, strategy_name)

        order = self._build_order(strategy_name, signal)
        if order is None:
            return None

        # Estimate max capital at risk for position sizing
        estimated_cost = self._estimate_cost(order, signal)

        return StrategyProposal(
            order=order,
            estimated_cost=estimated_cost,
            signal=signal,
            rationale=rationale,
        )

    # ── Gemini LLM Decision ─────────────────────────────────────────────────

    async def _ask_gemini(self, signal: SignalSnapshot) -> tuple[str, str]:
        """
        Ask Gemini to choose a strategy based on market context.
        Uses structured output to ensure a valid strategy name is returned.
        """
        prompt = f"""You are an expert options trader. Analyze this market signal and
choose the optimal strategy. Return ONLY a JSON object.

Market Signal:
  Symbol: {signal.symbol}
  Price: ${signal.price:.2f}
  RSI (14): {signal.rsi:.1f}
  IV Rank: {signal.iv_rank:.1f}%
  Current IV: {signal.current_iv:.1f}%
  Trend: {signal.trend}

Available strategies:
- iron_condor: 4-leg, sell OTM call spread + put spread. Best for HIGH IV Rank (>50) + neutral trend.
- bull_put_spread: Sell OTM put + buy lower put. Best for oversold (RSI<35) + HIGH IV Rank.
- bear_call_spread: Sell OTM call + buy higher call. Best for overbought (RSI>65) + HIGH IV Rank.
- protective_put: Buy OTM put hedge. Best for LOW IV Rank (<30) + portfolio risk.
- no_trade: Skip this symbol.

Respond with exactly this JSON:
{{"strategy": "<strategy_name>", "confidence": <0.0-1.0>, "rationale": "<1-2 sentence reason>"}}"""

        try:
            response = self.gemini_client.models.generate_content(
                model=config.gemini.model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,   # Low temperature for consistent decisions
                ),
            )
            import json
            data = json.loads(response.text)
            strategy = data.get("strategy", signal.recommended_strategy)
            rationale = data.get('rationale', '')
            full_rationale = f"[Gemini] {rationale} (confidence: {data.get('confidence', 0):.0%})"
            logger.info(
                f"Gemini selected {strategy} for {signal.symbol}",
                extra={"confidence": data.get("confidence")}
            )
            await self.state.add_log(f"[bold cyan]Gemini ({signal.symbol}):[/] {rationale} -> selected [bold yellow]{strategy}[/]")
            return strategy, full_rationale
        except Exception as e:
            logger.warning(f"Gemini call failed for {signal.symbol}: {e} — falling back to rules")
            strategy_name = signal.recommended_strategy
            await self.state.add_log(f"[bold magenta]Rules ({signal.symbol}):[/] Fallback rules selected [bold yellow]{strategy_name}[/]")
            return strategy_name, self._rule_rationale(signal, strategy_name)

    # ── Order Construction ──────────────────────────────────────────────────

    def _build_order(self, strategy_name: str, signal: SignalSnapshot) -> Optional[AnyOrder]:
        """Build the appropriate order object for the selected strategy."""
        group_id = str(uuid.uuid4())[:8]
        expiry = self._select_expiry()
        qty = 1  # Always start with 1 contract (position sizing via risk gate)

        if strategy_name == "iron_condor":
            return build_iron_condor(
                underlying=signal.symbol,
                underlying_price=signal.price,
                expiry=expiry,
                qty=qty,
                group_id=group_id,
            )
        elif strategy_name == "bull_put_spread":
            return build_bull_put_spread(
                underlying=signal.symbol,
                underlying_price=signal.price,
                expiry=expiry,
                qty=qty,
                group_id=group_id,
            )
        elif strategy_name == "bear_call_spread":
            return build_bear_call_spread(
                underlying=signal.symbol,
                underlying_price=signal.price,
                expiry=expiry,
                qty=qty,
                group_id=group_id,
            )
        elif strategy_name == "protective_put":
            return build_protective_put(
                underlying=signal.symbol,
                underlying_price=signal.price,
                expiry=expiry,
                qty=qty,
                group_id=group_id,
            )
        return None

    def _select_expiry(self) -> date:
        """Select an expiry ~30 DTE, landing on a Friday."""
        today = date.today()
        target = today + timedelta(days=30)
        # Roll forward to the next Friday
        days_to_friday = (4 - target.weekday()) % 7
        return target + timedelta(days=days_to_friday)

    @staticmethod
    def _estimate_cost(order: AnyOrder, signal: SignalSnapshot) -> float:
        """
        Estimate the maximum capital at risk for position sizing checks.
        Iron Condor/Spreads: wing width × 100 per contract.
        Protective Put: estimated premium ~2% of underlying price.
        """
        if isinstance(order, IronCondorOrder) and order.max_loss > 0:
            return order.max_loss
        if isinstance(order, CreditSpreadOrder) and order.max_loss > 0:
            return order.max_loss
        if isinstance(order, ProtectivePutOrder):
            return signal.price * 0.02 * 100  # ~2% of price = rough ATM put cost
        # Fallback: 5% of price per contract
        return signal.price * 0.05 * 100

    @staticmethod
    def _score_proposal(proposal: StrategyProposal) -> float:
        """
        Score a proposal for ranking. Higher is better.
        Favors: high IV rank (sell premium), strong RSI signal, neutral trend for condors.
        """
        sig = proposal.signal
        score = 0.0

        # High IV Rank = rich premium = better
        score += sig.iv_rank * 0.5

        # RSI extremes = directional opportunity
        if sig.rsi < 35:
            score += (35 - sig.rsi) * 0.3
        elif sig.rsi > 65:
            score += (sig.rsi - 65) * 0.3

        # Neutral trend bonus for Iron Condor
        if sig.trend == "neutral" and isinstance(proposal.order, IronCondorOrder):
            score += 10

        return score

    @staticmethod
    def _rule_rationale(signal: SignalSnapshot, strategy: str) -> str:
        return (f"[Rules] RSI={signal.rsi:.1f}, IVR={signal.iv_rank:.1f}%, "
                f"Trend={signal.trend} → {strategy}")
