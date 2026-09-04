import pytest
from core.state import AgentState, OptionPosition
from core.config import Config, RiskLimits
from agents.risk_guardian import RiskGuardian

@pytest.fixture
def state():
    s = AgentState()
    s.equity = 100000.0
    s.buying_power = 100000.0
    return s

@pytest.fixture
def risk_guardian():
    cfg = Config()
    cfg.risk.max_position_pct = 0.05
    cfg.risk.max_portfolio_delta = 0.20
    cfg.risk.daily_loss_limit_pct = 0.03
    return RiskGuardian(cfg)

def test_daily_loss_limit(risk_guardian, state):
    state.starting_balance = 100000.0
    # Simulate a loss of $3,500 (3.5% > 3.0% limit)
    state.daily_pnl = -3500.0
    
    passed, reason = risk_guardian.check_order(state, "iron_condor", estimated_cost=1000, estimated_delta=0.01)
    
    assert not passed
    assert "Daily loss limit" in reason
    assert state.trading_halted

def test_max_position_size(risk_guardian, state):
    # 5% of 100k is $5,000. Try an order that costs $6,000.
    passed, reason = risk_guardian.check_order(state, "iron_condor", estimated_cost=6000, estimated_delta=0.01)
    
    assert not passed
    assert "Position size" in reason

def test_portfolio_delta_limit(risk_guardian, state):
    # Try adding 0.25 delta to a 0.00 delta portfolio (limit is 0.20)
    passed, reason = risk_guardian.check_order(state, "bull_call_spread", estimated_cost=1000, estimated_delta=0.25)
    
    assert not passed
    assert "Portfolio delta" in reason

def test_successful_order(risk_guardian, state):
    # 0.01 delta, $1000 cost (1%). Should easily pass.
    passed, reason = risk_guardian.check_order(state, "iron_condor", estimated_cost=1000, estimated_delta=0.01)
    
    assert passed
    assert reason == "OK"
