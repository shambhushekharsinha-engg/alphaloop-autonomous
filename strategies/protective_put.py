"""
strategies/protective_put.py

Protective Put strategy.
Buys a single ATM or slightly OTM put as a portfolio hedge.

Deployed when:
  - The portfolio has significant long delta exposure and
  - IV Rank is LOW (< 30), meaning options are cheap to buy
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from strategies.iron_condor import OptionLeg, _build_occ_symbol, _round_to_strike


@dataclass
class ProtectivePutOrder:
    """A single long put as a protective hedge."""
    underlying: str
    expiry: date
    legs: List[OptionLeg] = field(default_factory=list)
    max_loss: float = 0.0    # Premium paid
    group_id: str = ""

    def is_valid(self) -> bool:
        return len(self.legs) == 1 and self.legs[0].side == "buy"


def build_protective_put(
    underlying: str,
    underlying_price: float,
    expiry: date,
    strike_pct: float = 0.97,   # Buy put at 97% of current price (3% OTM)
    qty: int = 1,
    available_contracts: Optional[List[dict]] = None,
    group_id: str = "",
) -> Optional[ProtectivePutOrder]:
    """
    Build a Protective Put order.

    Args:
        strike_pct: Strike as a fraction of current price (0.97 = 3% OTM put)
    """
    target_strike = _round_to_strike(underlying_price * strike_pct)

    if available_contracts:
        puts = [c for c in available_contracts
                if c.get("type") == "put"
                and c.get("expiration_date") == expiry.strftime("%Y-%m-%d")]
        # Find closest strike
        target_contract = min(
            puts,
            key=lambda c: abs(float(c.get("strike_price", 0)) - target_strike),
            default=None
        )
        if target_contract:
            target_strike = float(target_contract.get("strike_price", target_strike))

    leg = OptionLeg(
        symbol=_build_occ_symbol(underlying, expiry, "P", target_strike),
        underlying=underlying,
        right="P",
        strike=target_strike,
        expiry=expiry,
        side="buy",
        qty=qty,
        delta_target=-0.40,   # ~40Δ put for meaningful hedge
    )

    return ProtectivePutOrder(
        underlying=underlying,
        expiry=expiry,
        legs=[leg],
        max_loss=0.0,    # Set at execution from ask price
        group_id=group_id,
    )
