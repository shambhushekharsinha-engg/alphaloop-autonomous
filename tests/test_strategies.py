import pytest
from datetime import date
from strategies.iron_condor import build_iron_condor

def test_iron_condor_builder():
    order = build_iron_condor(
        underlying="SPY",
        underlying_price=500.0,
        expiry=date(2025, 1, 15),
        short_call_delta=0.20,
        short_put_delta=-0.20,
        wing_width_pct=0.02,
        qty=1,
        available_contracts=None, # Uses mock price-based strikes
        group_id="test"
    )
    
    assert order is not None
    assert len(order.legs) == 4
    assert order.legs[0].side == "sell"
    assert order.legs[1].side == "buy"
