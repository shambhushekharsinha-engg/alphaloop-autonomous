"""
strategies/credit_spread.py

Credit Spread strategy builder.

Two types supported:
  - Bull Put Spread: Sell OTM put, Buy lower OTM put → profits when underlying rises/stays flat
  - Bear Call Spread: Sell OTM call, Buy higher OTM call → profits when underlying falls/stays flat

Signal-driven selection:
  - RSI < 35 + IV Rank >= 40 → Bull Put Spread (oversold, sell puts below)
  - RSI > 65 + IV Rank >= 40 → Bear Call Spread (overbought, sell calls above)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from strategies.iron_condor import OptionLeg, _build_occ_symbol, _round_to_strike, _select_by_delta


@dataclass
class CreditSpreadOrder:
    """Represents a 2-leg credit spread order."""
    underlying: str
    spread_type: str      # "bull_put" or "bear_call"
    expiry: date
    legs: List[OptionLeg] = field(default_factory=list)
    max_profit: float = 0.0    # Net credit received ($)
    max_loss: float = 0.0      # Wing width × 100 − credit
    breakeven: float = 0.0
    group_id: str = ""

    def is_valid(self) -> bool:
        return len(self.legs) == 2 and all(leg.qty > 0 for leg in self.legs)


def build_bull_put_spread(
    underlying: str,
    underlying_price: float,
    expiry: date,
    short_put_delta: float = -0.30,  # Sell slightly OTM put
    wing_width_pct: float = 0.03,    # Buy put 3% further OTM
    qty: int = 1,
    available_contracts: Optional[List[dict]] = None,
    group_id: str = "",
) -> Optional[CreditSpreadOrder]:
    """
    Bull Put Spread: Sell OTM Put + Buy Lower OTM Put.
    Deployed when RSI < 35 (oversold) and IV Rank >= 40.
    Maximum profit = net credit; maximum loss = wing width - credit.
    """
    if available_contracts:
        puts = [c for c in available_contracts
                if c.get("type") == "put"
                and c.get("expiration_date") == expiry.strftime("%Y-%m-%d")]
        short_put_contract = _select_by_delta(puts, short_put_delta)
        if not short_put_contract:
            return None
        short_strike = float(short_put_contract.get("strike_price", 0))
    else:
        short_strike = _round_to_strike(underlying_price * (1 + short_put_delta * 0.5))

    long_strike = _round_to_strike(short_strike * (1 - wing_width_pct))
    wing_width = short_strike - long_strike

    legs = [
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "P", short_strike),
            underlying=underlying, right="P", strike=short_strike,
            expiry=expiry, side="sell", qty=qty, delta_target=short_put_delta,
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "P", long_strike),
            underlying=underlying, right="P", strike=long_strike,
            expiry=expiry, side="buy", qty=qty, delta_target=short_put_delta * 0.5,
        ),
    ]

    return CreditSpreadOrder(
        underlying=underlying,
        spread_type="bull_put",
        expiry=expiry,
        legs=legs,
        max_profit=0.0,      # Filled from live bid/ask at execution
        max_loss=wing_width * 100,
        breakeven=short_strike,
        group_id=group_id,
    )


def build_bear_call_spread(
    underlying: str,
    underlying_price: float,
    expiry: date,
    short_call_delta: float = 0.30,  # Sell slightly OTM call
    wing_width_pct: float = 0.03,    # Buy call 3% further OTM
    qty: int = 1,
    available_contracts: Optional[List[dict]] = None,
    group_id: str = "",
) -> Optional[CreditSpreadOrder]:
    """
    Bear Call Spread: Sell OTM Call + Buy Higher OTM Call.
    Deployed when RSI > 65 (overbought) and IV Rank >= 40.
    """
    if available_contracts:
        calls = [c for c in available_contracts
                 if c.get("type") == "call"
                 and c.get("expiration_date") == expiry.strftime("%Y-%m-%d")]
        short_call_contract = _select_by_delta(calls, short_call_delta)
        if not short_call_contract:
            return None
        short_strike = float(short_call_contract.get("strike_price", 0))
    else:
        short_strike = _round_to_strike(underlying_price * (1 + short_call_delta * 1.5))

    long_strike = _round_to_strike(short_strike * (1 + wing_width_pct))
    wing_width = long_strike - short_strike

    legs = [
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "C", short_strike),
            underlying=underlying, right="C", strike=short_strike,
            expiry=expiry, side="sell", qty=qty, delta_target=short_call_delta,
        ),
        OptionLeg(
            symbol=_build_occ_symbol(underlying, expiry, "C", long_strike),
            underlying=underlying, right="C", strike=long_strike,
            expiry=expiry, side="buy", qty=qty, delta_target=short_call_delta * 0.5,
        ),
    ]

    return CreditSpreadOrder(
        underlying=underlying,
        spread_type="bear_call",
        expiry=expiry,
        legs=legs,
        max_profit=0.0,
        max_loss=wing_width * 100,
        breakeven=short_strike,
        group_id=group_id,
    )
