import re

with open('web.py', 'r', encoding='utf-8') as f:
    content = f.read()

demo_loop = '''
import random
from core.models import Position

async def demo_market_maker_loop():
    await asyncio.sleep(5)
    while True:
        await asyncio.sleep(1.0)
        s = orchestrator.state
        
        # Give them a starter position if empty and dry_run is on
        if config.dry_run and len(s.positions) == 0 and s.signals:
            sig = list(s.signals.values())[0]
            fake_pos = Position(
                symbol=f"{sig.symbol}240920C00200000",
                underlying=sig.symbol,
                strategy="Credit Spread",
                side="sell",
                qty=10,
                avg_entry_price=2.50,
                current_price=2.50,
                unrealized_pnl=0.0,
                delta=-0.05,
                theta=12.50,
                group_id=f"grp_{sig.symbol}"
            )
            s.positions[fake_pos.symbol] = fake_pos
            s.open_position_count = 1
            s.buying_power -= 5000  # simulate collateral usage
            asyncio.create_task(s.add_log(f"🤖 [bold magenta]DEMO MODE:[/] Simulated execution of {fake_pos.strategy} on {sig.symbol} to demonstrate live P&L."))

        # Fluctuate existing positions
        async with s._lock:
            daily_pnl = 0.0
            for sym, pos in s.positions.items():
                change = pos.current_price * random.uniform(-0.005, 0.005)
                pos.current_price = max(0.01, pos.current_price + change)
                
                if pos.side == "sell":
                    pos.unrealized_pnl = (pos.avg_entry_price - pos.current_price) * pos.qty * 100
                else:
                    pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * pos.qty * 100
                
                daily_pnl += pos.unrealized_pnl
            
            s.daily_pnl = daily_pnl
            s.equity = s.starting_balance + daily_pnl
            s.portfolio_theta = sum(p.theta for p in s.positions.values())
            
            # Force fast chart updates for the demo (every 2 seconds)
            if len(s.equity_history) == 0 or (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(s.equity_history[-1]['time'].replace('Z', ''))).total_seconds() > 2:
                s.equity_history.append({
                    'time': datetime.datetime.utcnow().isoformat() + 'Z',
                    'equity': round(s.equity, 2)
                })
                if len(s.equity_history) > 60:
                    s.equity_history.pop(0)

# ── Lifecycle ────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
'''

content = content.replace(
'''# ── Lifecycle ────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():''', demo_loop)

content = content.replace(
'''    asyncio.create_task(orchestrator.run())''',
'''    asyncio.create_task(orchestrator.run())
    asyncio.create_task(demo_market_maker_loop())'''
)

with open('web.py', 'w', encoding='utf-8') as f:
    f.write(content)
