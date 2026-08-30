import pytest
from datetime import date
from core.state import AgentState
from agents.risk_guardian import RiskGuardianAgent
from strategies.protective_put import build_protective_put

@pytest.mark.asyncio
async def test_position_sizing_gate():
    state = AgentState(equity=100_000)
    guardian = RiskGuardianAgent(state)
    
    # Create an order that costs $6,000 (6% of equity, limit is 5%)
    order = build_protective_put("SPY", 500, date.today())
    cost = 6000.0
    
    decision = await guardian.evaluate(order, cost)
    assert not decision.allowed
    assert decision.gate_triggered == "position_size"

@pytest.mark.asyncio
async def test_daily_loss_limit_gate():
    state = AgentState(equity=96_000, starting_balance=100_000, daily_pnl=-4_000)
    guardian = RiskGuardianAgent(state)
    
    order = build_protective_put("SPY", 500, date.today())
    cost = 1000.0
    
    decision = await guardian.evaluate(order, cost)
    assert not decision.allowed
    assert decision.gate_triggered == "daily_loss"
    assert state.trading_halted
