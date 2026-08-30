"""
strategies/iron_condor.py

Iron Condor strategy builder.

An Iron Condor has 4 legs:
  - Short OTM Put  (sell)   ← collects premium
  - Long  OTM Put  (buy)    ← defines max loss (lower wing)
  - Short OTM Call (sell)   ← collects premium
  - Long  OTM Call (buy)    ← defines max loss (upper wing)

Best deployed when IV Rank is HIGH (≥ 50) and the underlying is expected
to stay range-bound (neutral trend, RSI between 40–60).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class OptionLeg:
    """Represents a single leg of a multi-leg options order."""
    symbol: str          # OCC-style: e.g. SPY240719P00530000
    underlying: str
    right: str           # "C" or "P"
    strike: float
    expiry: date
    side: str            # "buy" or "sell"
    qty: int
    delta_target: float  # The delta we aimed for when selecting this leg
    ratio_qty: int = 1   # For ratio spreads (future use)


@dataclass
class IronCondorOrder:
    """
    Represents a complete Iron Condor (4 legs) ready to submit.
    All legs share the same expiry and underlying.
    """
    underlying: str
    expiry: date
    legs: List[OptionLeg] = field(default_factory=list)
    max_profit: float = 0.0    # Net premium received (in $)
    max_loss: float = 0.0      # Width of wing × 100 − premium
    breakeven_low: float = 0.0
    breakeven_high: float = 0.0
    group_id: str = ""

    def is_valid(self) -> bool:
        """Validate that we have exactly 4 legs in the right configuration."""
        if len(self.legs) != 4:
            return False
        sides = {leg.side for leg in self.legs}
        rights = {leg.right for leg in self.legs}
        return sides == {"buy", "sell"} and rights == {"C", "P"}


def build_iron_condor(
    underlying: str,
    underlying_price: float,
    expiry: date,
    short_call_delta: float = 0.20,  # Sell ~20Δ OTM call
    short_put_delta: float = -0.20,  # Sell ~20Δ OTM put
    wing_width_pct: float = 0.02,    # Long strikes ~2% further OTM
    qty: int = 1,
    available_contracts: Optional[List[dict]] = None,  # From Alpaca options chain
    group_id: str = "",
) -> Optional[IronCondorOrder]:
    """
    Build an Iron Condor order by selecting strikes closest to target deltas.

    Args:
        underlying: The ticker symbol (e.g. "SPY")
        underlying_price: Current price of the underlying
        expiry: Target expiry date
        short_call_delta: Target delta for the short call (e.g. 0.20)
        short_put_delta: Target delta for the short put (e.g. -0.20)
        wing_width_pct: Percentage distance between short and long strikes
        qty: Number of contracts per leg
        available_contracts: List of contract dicts from Alpaca options chain
        group_id: Unique identifier tying all 4 legs together

    Returns:
        IronCondorOrder if successful, None if insufficient chain data
    """
    # If no live chain provided, use price-based approximation for testing
    if available_contracts is None:
        return _build_approximate_iron_condor(
            underlying, underlying_price, expiry,
            short_call_delta, short_put_delta, wing_width_pct, qty, group_id
        )

    # Filter contracts for the target expiry
    expiry_str = expiry.strftime("%Y-%m-%d")
    calls = [c for c in available_contracts if c.get("type") == "call"
             and c.get("expiration_date") == expiry_str]
    puts = [c for c in available_contracts if c.get("type") == "put"
            and c.get("expiration_date") == expiry_str]

    if not calls or not puts:
        return None

    # Select short call: strike closest to short_call_delta
    short_call_contract = _select_by_delta(calls, short_call_delta)
    # Select short put: strike closest to short_put_delta
    short_put_contract = _select_by_delta(puts, short_put_delta)

    if not short_call_contract or not short_put_contract:
        return None

    short_call_strike = float(short_call_contract.get("strike_price", 0))
    short_put_strike = float(short_put_contract.get("strike_price", 0))

    # Long strikes are further OTM by wing_width_pct
    long_call_strike = _round_to_strike(short_call_strike * (1 + wing_width_pct))
    long_put_strike = _round_to_strike(short_put_strike * (1 - wing_width_pct))

    short_call_iv = short_call_contract.get("implied_volatility", 0)
    short_put_iv = short_put_contract.get("implied_volatility", 0)
    net_credit = (
        float(short_call_contract.get("bid_price", 0)) +
        float(short_put_contract.get("bid_price", 0))
    ) * 100  # Approximate — long wings reduce this slightly

    wing_width = short_call_strike - long_call_strike  # Same on both sides ideally
    max_loss = (wing_width * 100) - net_credit

    legs = [
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "C", short_call_strike),
            underlying=underlying, right="C", strike=short_call_strike,
            expiry=expiry, side="sell", qty=qty,
            delta_target=short_call_delta
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "C", long_call_strike),
            underlying=underlying, right="C", strike=long_call_strike,
            expiry=expiry, side="buy", qty=qty,
            delta_target=short_call_delta * 0.5
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "P", short_put_strike),
            underlying=underlying, right="P", strike=short_put_strike,
            expiry=expiry, side="sell", qty=qty,
            delta_target=short_put_delta
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "P", long_put_strike),
            underlying=underlying, right="P", strike=long_put_strike,
            expiry=expiry, side="buy", qty=qty,
            delta_target=short_put_delta * 0.5
        ),
    ]

    order = IronCondorOrder(
        underlying=underlying,
        expiry=expiry,
        legs=legs,
        max_profit=net_credit,
        max_loss=max_loss,
        breakeven_low=short_put_strike - (net_credit / 100),
        breakeven_high=short_call_strike + (net_credit / 100),
        group_id=group_id,
    )
    return order if order.is_valid() else None


def _select_by_delta(contracts: List[dict], target_delta: float) -> Optional[dict]:
    """Return the contract whose greeks delta is closest to target_delta."""
    best = None
    best_dist = float("inf")
    for c in contracts:
        greeks = c.get("greeks") or {}
        delta = float(greeks.get("delta", 999))
        dist = abs(delta - target_delta)
        if dist < best_dist:
            best_dist = dist
            best = c
    return best


def _round_to_strike(price: float, increment: float = 1.0) -> float:
    """Round a price to the nearest standard strike increment."""
    return round(price / increment) * increment


def _build_occ_symbol(underlying: str, expiry: date, right: str, strike: float) -> str:
    """Build a standard OCC option symbol: e.g. SPY240719C00450000"""
    expiry_str = expiry.strftime("%y%m%d")
    strike_str = f"{int(strike * 1000):08d}"
    return f"{underlying.ljust(6)}{expiry_str}{right}{strike_str}"


def _build_approximate_iron_condor(
    underlying: str, price: float, expiry: date,
    short_call_delta: float, short_put_delta: float,
    wing_width_pct: float, qty: int, group_id: str
) -> IronCondorOrder:
    """
    Fallback builder using price approximation when live chain data is unavailable.
    Uses a simplified model: short strikes at ±8% OTM, wings ±2% further.
    """
    short_call_strike = _round_to_strike(price * 1.08)
    long_call_strike = _round_to_strike(price * (1.08 + wing_width_pct))
    short_put_strike = _round_to_strike(price * 0.92)
    long_put_strike = _round_to_strike(price * (0.92 - wing_width_pct))

    legs = [
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "C", short_call_strike),
            underlying=underlying, right="C", strike=short_call_strike,
            expiry=expiry, side="sell", qty=qty, delta_target=short_call_delta
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "C", long_call_strike),
            underlying=underlying, right="C", strike=long_call_strike,
            expiry=expiry, side="buy", qty=qty, delta_target=short_call_delta * 0.5
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "P", short_put_strike),
            underlying=underlying, right="P", strike=short_put_strike,
            expiry=expiry, side="sell", qty=qty, delta_target=short_put_delta
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "P", long_put_strike),
            underlying=underlying, right="P", strike=long_put_strike,
            expiry=expiry, side="buy", qty=qty, delta_target=short_put_delta * 0.5
        ),
    ]
    return IronCondorOrder(
        underlying=underlying, expiry=expiry, legs=legs,
        max_profit=0.0, max_loss=0.0, group_id=group_id
    )
