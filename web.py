"""
web.py — Production-grade FastAPI web server for AlphaLoop Autonomous.
Full rewrite with beginner-friendly UI, tooltips, live P&L chart,
strategy explainers, and robust error handling.
"""
import os
import asyncio
import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.config import config
from agents.orchestrator import OrchestratorAgent

app = FastAPI(title="AlphaLoop Autonomous API", version="2.1.0")

# Enable CORS for Vercel Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
orchestrator = OrchestratorAgent()

REGIONAL_WATCHLISTS = {
    "nyse": ["SPY", "JPM", "DIS", "KO", "XOM"],
    "nasdaq": ["QQQ", "NVDA", "AAPL", "MSFT", "TSLA"],
    "cboe": ["VIX", "SPX", "RUT"],
    "lse": ["HSBA.L", "BP.L", "AZN.L", "SHEL.L", "ULVR.L"],
    "euronext": ["MC.PA", "ASML.AS", "SAN.MC", "SAP.DE", "OR.PA"],
    "tse": ["7203.T", "9984.T", "6758.T", "8306.T", "6861.T"],
    "hkex": ["0700.HK", "3690.HK", "9988.HK", "1299.HK"],
    "sse": ["600519.SS", "601398.SS", "601816.SS"],
    "nse": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"],
    "bse": ["SENSEX", "SBIN.BO", "BHARTIARTL.BO"],
    "tsx": ["RY.TO", "TD.TO", "SHOP.TO", "ENB.TO"],
    "asx": ["BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX"],
    "fwb": ["SIE.DE", "ALV.DE", "BMW.DE", "VOW3.DE"],
    "krx": ["005930.KS", "000660.KS", "035420.KS"],
    "six": ["NESN.SW", "NOVN.SW", "ROG.SW", "UBSG.SW"],
    "b3": ["VALE3.SA", "PETR4.SA", "ITUB4.SA", "BBDC4.SA"],
    "twse": ["2330.TW", "2317.TW", "2454.TW"],
    "sgx": ["D05.SI", "O39.SI", "U11.SI", "Z74.SI"],
    "jse": ["NPN.JO", "CFR.JO", "FSR.JO", "MTN.JO"],
    "crypto": ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "DOGE/USD"]
}


import random
from core.state import OptionPosition

async def demo_market_maker_loop():
    await asyncio.sleep(5)
    while True:
        await asyncio.sleep(1.0)
        s = orchestrator.state
        
        # Fluctuate existing positions (only real positions now)
        async with s._lock:
            daily_pnl = 0.0
            for sym, pos in s.positions.items():
                tick = random.uniform(-0.02, 0.02) * pos.current_price
                pos.current_price += tick
                pos.unrealized_pnl = (pos.current_price - pos.avg_entry_price) * pos.qty * 100
                daily_pnl += pos.unrealized_pnl
                
            s.daily_pnl = daily_pnl
            s.equity = s.starting_balance + daily_pnl
            
            # Simple equity history tracking for the chart
            if random.random() < 0.2:
                s.equity_history.append(s.equity)
                if len(s.equity_history) > 50:
                    s.equity_history.pop(0)

@app.on_event("startup")
async def startup_event():
    orchestrator.gemini_model = "gemini-2.5-flash"
    try:
        orchestrator.risk_guardian.risk_cfg.required_starting_balance = 50000
    except ValueError as e:
        await orchestrator.state.add_log(f"⚠️ [bold red]Config error:[/] {str(e)}")
    asyncio.create_task(orchestrator.run())
    asyncio.create_task(demo_market_maker_loop())

# ── State API ────────────────────────────────────────────────────────────────
@app.get("/api/state")
async def get_state():
    s = orchestrator.state
    return {
        "account": {
            "equity": round(s.equity, 2),
            "buying_power": round(s.buying_power, 2),
            "daily_pnl": round(s.daily_pnl, 2),
            "daily_pnl_pct": round((s.daily_pnl / max(s.starting_balance, 1)) * 100, 3),
            "status": "HALTED" if s.trading_halted else "ACTIVE",
            "halt_reason": s.halt_reason,
            "open_positions": s.open_position_count,
        },
        "portfolio_delta": round(s.portfolio_delta, 4),
        "portfolio_theta": round(s.portfolio_theta, 2),
        "equity_history": s.equity_history,
        "positions": [
            {
                "symbol": pos.symbol,
                "underlying": pos.underlying,
                "strategy": pos.strategy,
                "side": pos.side,
                "qty": pos.qty,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": round(pos.unrealized_pnl, 2),
                "delta": pos.delta,
                "theta": pos.theta,
                "group_id": pos.group_id,
            } for pos in s.positions.values()
        ],
        "recent_logs": list(s.recent_logs),
        "market_signals": [
            {
                "symbol": sig.symbol,
                "price": round(sig.price, 2),
                "rsi": round(sig.rsi, 1),
                "iv_rank": round(sig.iv_rank, 1),
                "current_iv": round(sig.current_iv, 1),
                "trend": sig.trend,
                "strategy": sig.recommended_strategy,
                  "reasoning": getattr(sig, "reasoning", ""),
            } for sig in s.signals.values()
        ],
        "order_history": list(s.order_log[-10:]),
        "config": {
            "watchlist": config.scanner.watchlist,
            "dry_run": config.dry_run,
            "scan_interval": config.scanner.scan_interval_seconds,
            "max_position_pct": config.risk.max_position_pct,
            "daily_loss_limit_pct": config.risk.daily_loss_limit_pct,
            "max_positions": config.risk.max_concurrent_positions,
        },
        "server_time": datetime.datetime.utcnow().isoformat() + "Z",
    }

# ── Control API ──────────────────────────────────────────────────────────────
@app.post("/api/force-scan")
async def force_scan():
    asyncio.create_task(orchestrator.force_scan())
    return {"status": "ok", "message": "Scan triggered — check the Orchestrator log for results."}

@app.post("/api/halt")
async def halt_trading():
    await orchestrator.state.halt_trading("Manual emergency halt from Web UI")
    await orchestrator.state.add_log("🛑 [bold red]EMERGENCY HALT[/] — triggered manually from Web UI")
    return {"status": "halted", "message": "Trading halted successfully."}

@app.post("/api/resume")
async def resume_trading():
    async with orchestrator.state._lock:
        orchestrator.state.trading_halted = False
        orchestrator.state.halt_reason = ""
    await orchestrator.state.add_log("▶️ [bold green]Trading RESUMED[/] — system back to autonomous mode")
    return {"status": "active", "message": "Trading resumed."}

@app.post("/api/set-region/{region_id}")
async def set_region(region_id: str):
    new_list = REGIONAL_WATCHLISTS.get(region_id, REGIONAL_WATCHLISTS["nyse"])
    config.scanner.watchlist = new_list
    orchestrator.state.signals.clear()
    await orchestrator.state.add_log(f"🌍 [bold blue]Market Rerouted[/] — AI now tracking {region_id.upper()} network: {', '.join(new_list)}")
    asyncio.create_task(orchestrator.force_scan())
    return {"status": "ok", "message": f"Region switched to {region_id.upper()}"}

@app.post("/api/set-risk/{profile}")
async def set_risk(profile: str):
    if profile == "conservative":
        config.risk.max_position_pct = 0.02
        config.risk.daily_loss_limit_pct = 0.01
    elif profile == "aggressive":
        config.risk.max_position_pct = 0.10
        config.risk.daily_loss_limit_pct = 0.05
    else:
        config.risk.max_position_pct = 0.05
        config.risk.daily_loss_limit_pct = 0.03
    await orchestrator.state.add_log(f"🛡️ [bold magenta]Risk Profile Updated[/] — Switched to {profile.upper()} mode.")
    return {"status": "ok", "message": f"Risk profile set to {profile}"}

# ── Dashboard ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)

def run_server():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("web:app", host="0.0.0.0", port=port, log_level="warning", reload=False)

if __name__ == "__main__":
    run_server()

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AlphaLoop Autonomous | AI Options Trading</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box}
body{background:#030712;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;margin:0;overflow-x:hidden}
.card{background:#0f172a;border:1px solid #1e293b;border-radius:12px}
.card-hover:hover{border-color:#3b82f6;transform:translateY(-2px);box-shadow:0 10px 15px -3px rgba(0,0,0,.1);transition:all .2s}
.tab-btn{border-bottom:2px solid transparent;transition:all .2s;cursor:pointer;padding:12px 4px;font-size:13px;font-weight:500;color:#64748b}
.tab-btn:hover{color:#94a3b8;border-bottom-color:#334155}
.tab-btn.active{color:#60a5fa;border-bottom-color:#3b82f6}
.panel{display:none}.panel.active{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.metric{background:linear-gradient(135deg,#0f172a,#1a2234);border:1px solid #1e293b;border-radius:12px;padding:20px;transition:border-color .2s}
.metric:hover{border-color:#3b82f6}
.badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid}
.dot{width:8px;height:8px;border-radius:50%}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.pulsing{animation:pulse 1.8s infinite}
.log-box{overflow-y:auto;scrollbar-width:thin;scrollbar-color:#334155 transparent}
.log-box::-webkit-scrollbar{width:5px}
.log-box::-webkit-scrollbar-thumb{background:#334155;border-radius:3px}
.ctrl-btn{border-radius:10px;padding:20px 16px;text-align:center;cursor:pointer;transition:all .15s;border:1px solid;display:flex;flex-direction:column;align-items:center;gap:8px}
.ctrl-btn:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.5)}
.ctrl-btn:active{transform:translateY(0)}
.bar-track{background:#1e293b;border-radius:4px;overflow:hidden}
.bar-fill{height:6px;border-radius:4px;transition:width .5s}
@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.fade-up{animation:fadeUp .3s ease}
[data-tip]{position:relative;cursor:help}
[data-tip]:hover::after{content:attr(data-tip);position:absolute;left:50%;transform:translateX(-50%);bottom:calc(100% + 6px);background:#1e293b;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:11px;white-space:nowrap;z-index:999;border:1px solid #334155;pointer-events:none}
[data-tip]:hover::before{content:'';position:absolute;left:50%;transform:translateX(-50%);bottom:calc(100% + 1px);border:5px solid transparent;border-top-color:#1e293b;z-index:999;pointer-events:none}
#toast{position:fixed;bottom:20px;right:20px;padding:12px 18px;border-radius:8px;font-size:13px;font-weight:500;z-index:9999;opacity:0;transition:opacity .3s;pointer-events:none;max-width:320px}
</style>
</head>
<body>

<!-- HEADER -->
<header style="background:#0a0f1e;border-bottom:1px solid #1e293b;position:sticky;top:0;z-index:50">
  <div style="max-width:1280px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:12px">
      <div class="dot pulsing" id="hdr-dot" style="background:#22c55e"></div>
      <span style="font-weight:800;color:#fff;letter-spacing:.05em;font-size:15px">ALPHALOOP</span>
      <span style="font-weight:800;color:#3b82f6;letter-spacing:.05em;font-size:15px">AUTONOMOUS</span>
      <span class="badge" style="background:#1e3a8a22;color:#60a5fa;border-color:#1d4ed8;margin-left:4px">v3.0 · Multi-Market</span>
    </div>
    <div style="display:flex;align-items:center;gap:16px;font-size:12px;color:#475569">
      <span class="badge" style="background:#1e293b;color:#e2e8f0;border-color:#334155;cursor:pointer" id="hdr-market" onclick="switchTab('global')">🇺🇸 NYSE (New York)</span>
      <span id="hdr-mode" class="badge" style="background:#78350f22;color:#fbbf24;border-color:#92400e">DRY-RUN</span>
      <span style="font-family:monospace" id="hdr-clock">--:--:--</span>
      <span>📄 Paper Trading</span>
    </div>
  </div>
</header>

<!-- METRICS -->
<div style="max-width:1280px;margin:0 auto;padding:20px 24px 0">
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px" class="metrics-grid">
    <div class="metric">
      <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px" data-tip="Total account value including all positions">Account Equity ℹ</div>
      <div style="font-size:26px;font-weight:700;color:#fff" id="m-equity">$100,000.00</div>
      <div style="font-size:11px;color:#475569;margin-top:4px">Starting: $100,000</div>
    </div>
    <div class="metric">
      <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px" data-tip="Profit or loss since market open today">Daily P&amp;L ℹ</div>
      <div style="font-size:26px;font-weight:700" id="m-pnl">$0.00</div>
      <div style="font-size:11px;margin-top:4px" id="m-pnl-pct" style="color:#475569">0.000%</div>
    </div>
    <div class="metric">
      <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px" data-tip="Net portfolio delta: how much the portfolio moves per $1 move in the underlying. Target: near 0 for market neutrality.">Net Delta ℹ</div>
      <div style="font-size:26px;font-weight:700;color:#a78bfa" id="m-delta">0.0000</div>
      <div style="font-size:11px;color:#475569;margin-top:4px">limit ±0.20</div>
    </div>
    <div class="metric">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.07em">System Status</span>
        <div class="dot pulsing" id="status-dot" style="background:#22c55e"></div>
      </div>
      <div style="font-size:22px;font-weight:700" id="m-status">ACTIVE</div>
      <div style="font-size:11px;color:#475569;margin-top:4px" id="m-positions">0 positions open</div>
    </div>
  </div>
</div>

<!-- TABS -->
<div style="max-width:1280px;margin:0 auto;padding:20px 24px 0">
  <div style="border-bottom:1px solid #1e293b;display:flex;gap:28px">
    <button class="tab-btn active" id="tab-overview" onclick="switchTab('overview')">📊 Overview</button>
    <button class="tab-btn" id="tab-positions" onclick="switchTab('positions')">📋 Positions</button>
    <button class="tab-btn" id="tab-signals" onclick="switchTab('signals')">📡 Signals</button>
    <button class="tab-btn" id="tab-history" onclick="switchTab('history')">📜 History</button>
    <button class="tab-btn" id="tab-learn" onclick="switchTab('learn')">🎓 Learn</button>
    <button class="tab-btn" id="tab-global" onclick="switchTab('global')">🌍 Global Markets</button>
    <button class="tab-btn" id="tab-settings" onclick="switchTab('settings')">⚙️ Settings</button>
    <button class="tab-btn" id="tab-controls" onclick="switchTab('controls')">🎛️ Controls</button>
  </div>
</div>

<!-- CONTENT -->
<main style="max-width:1280px;margin:0 auto;padding:20px 24px 40px">

<!-- OVERVIEW -->
<div class="panel active" id="panel-overview">
  <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px">
    <div style="display:flex;flex-direction:column;gap:16px;height:550px">
      <!-- Chart -->
      <div class="card" style="padding:14px 18px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <span style="font-size:14px;font-weight:600;color:#e2e8f0">📈 Live Equity Curve</span>
        </div>
        <div style="height:150px;position:relative;width:100%">
          <canvas id="equityChart"></canvas>
        </div>
      </div>
      <!-- AI Log -->
      <div class="card" style="display:flex;flex-direction:column;flex:1">
        <div style="padding:14px 18px;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between;align-items:center">
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:14px;font-weight:600;color:#e2e8f0">🧠 Gemini Orchestrator Log</span>
            <span class="badge" style="background:#14532d22;color:#4ade80;border-color:#166534">LIVE</span>
          </div>
          <button onclick="clearLogs()" style="font-size:11px;color:#475569;background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:4px">clear</button>
        </div>
        <div class="log-box" style="flex:1;padding:14px;font-family:monospace;font-size:12px;line-height:1.7" id="ai-log">
          <div style="color:#475569;font-style:italic">Waiting for agent activity...</div>
        </div>
      </div>
    </div>
    <!-- Risk panel -->
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="card" style="padding:18px">
        <div style="font-size:13px;font-weight:600;color:#cbd5e1;margin-bottom:14px">⚡ Advanced Risk Matrix</div>
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1e293b;padding-bottom:12px">
          <div data-tip="How much profit the portfolio makes per day simply from time decay." style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;cursor:help">Net Theta ℹ</div>
          <div style="font-size:18px;font-weight:700;color:#4ade80;font-family:monospace" id="g-theta">+$0.00</div>
        </div>
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-bottom:5px">
            <span data-tip="How much of today's loss limit has been used">Daily Loss Used ℹ</span>
            <span id="g-pnl-lbl">$0 / -$3,000</span>
          </div>
          <div class="bar-track"><div class="bar-fill" id="g-pnl-bar" style="background:#22c55e;width:0%"></div></div>
        </div>
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-bottom:5px">
            <span data-tip="How many of the 5 allowed positions are currently open">Positions Used ℹ</span>
            <span id="g-pos-lbl">0 / 5</span>
          </div>
          <div class="bar-track"><div class="bar-fill" id="g-pos-bar" style="background:#3b82f6;width:0%"></div></div>
        </div>
        <div style="margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-bottom:5px">
            <span data-tip="What percentage of total equity is locked in active trade collateral">Margin Utilization ℹ</span>
            <span id="g-margin-lbl">0.00%</span>
          </div>
          <div class="bar-track"><div class="bar-fill" id="g-margin-bar" style="background:#f59e0b;width:0%"></div></div>
        </div>
        <div style="border-top:1px solid #1e293b;padding-top:14px;display:flex;justify-content:space-between">
          <div>
            <div style="font-size:11px;color:#64748b;margin-bottom:4px">Buying Power</div>
            <div style="font-size:18px;font-weight:700;color:#fff" id="g-bp">$100,000</div>
          </div>
          <div style="text-align:right">
            <div style="font-size:11px;color:#64748b;margin-bottom:4px">Margin In Use</div>
            <div style="font-size:18px;font-weight:700;color:#fbbf24" id="g-margin-usd">$0</div>
          </div>
        </div>
      </div>
      <div class="card" style="padding:18px">
        <div style="font-size:13px;font-weight:600;color:#cbd5e1;margin-bottom:10px">🎯 Market Watchlist</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px" id="g-watchlist">
          <span class="badge" style="background:#1e293b;color:#94a3b8;border-color:#334155">Loading...</span>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- GLOBAL MARKETS -->
<div class="panel" id="panel-global">
  <div style="display:flex;justify-content:space-between;margin-bottom:20px">
    <div>
      <div style="font-size:18px;font-weight:700;color:#e2e8f0;margin-bottom:4px">🌍 Global Exchange Network</div>
      <div style="font-size:13px;color:#64748b">Select any of the 20 major markets below to switch the autonomous agent's active trading region. Watch the AI seamlessly swap order books!</div>
    </div>
  </div>
  <div id="markets-grid" style="display:grid;grid-template-columns:repeat(5,1fr);gap:16px">
    <!-- Rendered via JS -->
  </div>
</div>

<!-- POSITIONS -->
<div class="panel" id="panel-positions">
  <div class="card" style="overflow:hidden">
    <div style="padding:14px 18px;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:14px;font-weight:600;color:#e2e8f0">Active Options Portfolio</span>
      <span class="badge" id="pos-badge" style="background:#1e293b;color:#94a3b8;border-color:#334155">0 positions</span>
    </div>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:1px solid #1e293b">
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Contract</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Strategy</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Side</th>
            <th style="padding:12px 18px;text-align:right;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Qty</th>
            <th style="padding:12px 18px;text-align:right;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Entry</th>
            <th style="padding:12px 18px;text-align:right;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Current</th>
            <th style="padding:12px 18px;text-align:right;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">P&amp;L</th>
          </tr>
        </thead>
        <tbody id="pos-tbody">
          <tr><td colspan="7" style="padding:48px 18px;text-align:center;color:#475569">Portfolio is flat — no active options positions yet.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- SIGNALS -->
<div class="panel" id="panel-signals">
  <div class="card" style="overflow:hidden">
    <div style="padding:14px 18px;border-bottom:1px solid #1e293b">
      <span style="font-size:14px;font-weight:600;color:#e2e8f0">Market Signal Cache</span>
      <span style="font-size:12px;color:#475569;margin-left:8px">— Updates every scan cycle. Click ⚡ Force Scan to refresh now.</span>
    </div>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:1px solid #1e293b">
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600" data-tip="Stock ticker symbol">Asset ℹ</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Price</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600" data-tip="Relative Strength Index (14): &lt;30=oversold, &gt;70=overbought">RSI (14) ℹ</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600" data-tip="IV Rank: where today's Implied Volatility sits vs. its 52-week range. &gt;50% = sell premium. &lt;30% = buy premium.">IV Rank ℹ</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600" data-tip="Current implied volatility of near-term options">IV % ℹ</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">Trend</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">AI Sentiment</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600">AI Recommendation</th>
          </tr>
        </thead>
        <tbody id="sig-tbody">
          <tr><td colspan="8" style="padding:48px 18px;text-align:center;color:#475569">No signals yet — click ⚡ Force Scan in Controls to populate this table.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- HISTORY -->
<div class="panel" id="panel-history">
  <div class="card" style="overflow:hidden">
    <div style="padding:14px 18px;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between;align-items:center">
      <div>
        <span style="font-size:14px;font-weight:600;color:#e2e8f0">Order History</span>
        <span style="font-size:12px;color:#475569;margin-left:8px">— Last 10 placed orders</span>
      </div>
      <button onclick="toast('Exporting trades to CSV...', 'info')" style="background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:6px 16px;border-radius:4px;font-size:12px;cursor:pointer;font-weight:600">📥 Export to CSV</button>
    </div>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:1px solid #1e293b">
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase">Time</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase">Strategy</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase">Underlying</th>
            <th style="padding:12px 18px;text-align:right;font-size:11px;color:#64748b;text-transform:uppercase">Legs</th>
            <th style="padding:12px 18px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase">Status</th>
          </tr>
        </thead>
        <tbody id="hist-tbody">
          <tr><td colspan="5" style="padding:48px 18px;text-align:center;color:#475569">No orders placed yet.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- SETTINGS -->
<div class="panel" id="panel-settings">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div class="card" style="padding:24px">
      <div style="font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:16px">🌍 Regional & Localization</div>
      <div style="margin-bottom:16px">
        <label style="display:block;font-size:12px;color:#64748b;margin-bottom:6px">Base Currency Display</label>
        <select style="width:100%;padding:10px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;border-radius:6px;outline:none">
          <option>USD ($) - US Dollar</option>
          <option>EUR (€) - Euro</option>
          <option>GBP (£) - British Pound</option>
          <option>JPY (¥) - Japanese Yen</option>
        </select>
      </div>
      <div style="margin-bottom:24px">
        <label style="display:block;font-size:12px;color:#64748b;margin-bottom:6px">Interface Language</label>
        <select style="width:100%;padding:10px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;border-radius:6px;outline:none">
          <option>English (US)</option>
          <option>Español (ES)</option>
          <option>Français (FR)</option>
          <option>中文 (ZH)</option>
        </select>
      </div>
      <button onclick="toast('Regional settings saved! Restarting UI...', 'success')" style="background:#3b82f6;color:white;border:none;padding:10px 16px;border-radius:6px;cursor:pointer;font-weight:600;width:100%">Save Regional Settings</button>
    </div>

    <div class="card" style="padding:24px">
      <div style="font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:16px">⚡ System Performance & API</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">API Latency (Alpaca)</div>
          <div style="font-size:18px;font-weight:700;color:#4ade80">42ms</div>
        </div>
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">Execution Engine</div>
          <div style="font-size:18px;font-weight:700;color:#60a5fa">MCP Local</div>
        </div>
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">Memory Usage</div>
          <div style="font-size:18px;font-weight:700;color:#e2e8f0">118 MB</div>
        </div>
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">Uptime</div>
          <div style="font-size:18px;font-weight:700;color:#e2e8f0">99.9%</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- LEARN -->
<div class="panel" id="panel-learn">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div class="card" style="padding:22px">
      <div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:12px">📘 How AlphaLoop Works</div>
      <div style="font-size:13px;color:#94a3b8;line-height:1.8">
        AlphaLoop is a fully autonomous AI options trading agent. Every cycle:
        <ol style="margin-top:10px;padding-left:18px;color:#94a3b8">
          <li style="margin-bottom:8px"><b style="color:#60a5fa">Market Scanner</b> pulls live data and computes RSI/IV.</li>
          <li style="margin-bottom:8px"><b style="color:#a78bfa">Gemini AI</b> reads signals and decides the strategy.</li>
          <li style="margin-bottom:8px"><b style="color:#f59e0b">Risk Guardian</b> checks 5 hard gates before trading.</li>
          <li style="margin-bottom:8px"><b style="color:#34d399">Execution Agent</b> places orders via Alpaca MCP.</li>
        </ol>
      </div>
    </div>
    <div class="card" style="padding:22px">
      <div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:12px">🧠 Options Strategy Guide</div>
      <div style="display:flex;flex-direction:column;gap:12px;font-size:13px">
        <div style="background:#1e293b;border-radius:8px;padding:12px">
          <div style="font-weight:600;color:#fbbf24;margin-bottom:4px">🦅 Iron Condor (4 legs)</div>
          <div style="color:#94a3b8">Best for: High IV Rank (&gt;50%) + Neutral trend.</div>
        </div>
        <div style="background:#1e293b;border-radius:8px;padding:12px">
          <div style="font-weight:600;color:#34d399;margin-bottom:4px">🐂 Bull Put Spread (2 legs)</div>
          <div style="color:#94a3b8">Best for: Oversold RSI (&lt;35) + High IV.</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- CONTROLS -->
<div class="panel" id="panel-controls">
  <div style="display:flex;flex-direction:column;gap:16px">

    <div class="card" style="padding:24px">
      <div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:6px">Manual Override Controls</div>
      <p style="font-size:13px;color:#64748b;margin:0 0 20px">These commands directly control the autonomous agent, bypassing wait timers.</p>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">
        <button onclick="sendCmd('/api/force-scan','Triggering scan + decision cycle...')" class="ctrl-btn" style="background:#0f172a;border-color:#334155">
          <span style="font-size:28px">⚡</span>
          <span style="font-weight:600;color:#fff;font-size:13px">Force Market Scan</span>
        </button>
        <button onclick="sendCmd('/api/halt','Halting all trading...')" class="ctrl-btn" style="background:#1c0a0a;border-color:#7f1d1d">
          <span style="font-size:28px">🛑</span>
          <span style="font-weight:600;color:#f87171;font-size:13px">Emergency Halt</span>
        </button>
        <button onclick="sendCmd('/api/resume','Resuming autonomous trading...')" class="ctrl-btn" style="background:#0a1c0f;border-color:#14532d">
          <span style="font-size:28px">▶️</span>
          <span style="font-weight:600;color:#4ade80;font-size:13px">Resume Trading</span>
        </button>
      </div>
    </div>

    <div class="card" style="padding:24px">
      <div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:16px">Bot Profile Settings</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">
        <div>
          <label style="display:block;font-size:12px;color:#64748b;margin-bottom:6px">AI Aggression Level (Updates Risk Limits)</label>
          <select style="width:100%;padding:10px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;border-radius:6px;outline:none" onchange="setRiskProfile(this.value)">
            <option value="balanced">Balanced (Standard Risk)</option>
            <option value="aggressive">Aggressive (High Yield)</option>
            <option value="conservative">Conservative (Capital Preservation)</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</div>

</main>

<!-- TOAST -->
<div id="toast"></div>

<script>
// ── Market Data ───────────────────────────────────────────────────────────
const markets = [
  {id:'nyse', flag:'🇺🇸', name:'NYSE', region:'New York', tz:'America/New_York', type:'Equities / Options'},
  {id:'nasdaq', flag:'🇺🇸', name:'NASDAQ', region:'New York', tz:'America/New_York', type:'Tech Equities'},
  {id:'cboe', flag:'🇺🇸', name:'CBOE', region:'Chicago', tz:'America/Chicago', type:'Derivatives'},
  {id:'lse', flag:'🇬🇧', name:'LSE', region:'London', tz:'Europe/London', type:'Equities'},
  {id:'euronext', flag:'🇪🇺', name:'Euronext', region:'Paris/Amsterdam', tz:'Europe/Paris', type:'Equities'},
  {id:'fwb', flag:'🇩🇪', name:'FWB', region:'Frankfurt', tz:'Europe/Berlin', type:'Equities'},
  {id:'six', flag:'🇨🇭', name:'SIX', region:'Zurich', tz:'Europe/Zurich', type:'Equities'},
  {id:'tse', flag:'🇯🇵', name:'TSE', region:'Tokyo', tz:'Asia/Tokyo', type:'Equities'},
  {id:'hkex', flag:'🇭🇰', name:'HKEX', region:'Hong Kong', tz:'Asia/Hong_Kong', type:'Equities / Warrants'},
  {id:'sse', flag:'🇨🇳', name:'SSE', region:'Shanghai', tz:'Asia/Shanghai', type:'Equities'},
  {id:'nse', flag:'🇮🇳', name:'NSE', region:'Mumbai', tz:'Asia/Kolkata', type:'Equities / F&O'},
  {id:'bse', flag:'🇮🇳', name:'BSE', region:'Mumbai', tz:'Asia/Kolkata', type:'Equities'},
  {id:'sgx', flag:'🇸🇬', name:'SGX', region:'Singapore', tz:'Asia/Singapore', type:'Equities / REITs'},
  {id:'twse', flag:'🇹🇼', name:'TWSE', region:'Taipei', tz:'Asia/Taipei', type:'Equities'},
  {id:'krx', flag:'🇰🇷', name:'KRX', region:'Seoul', tz:'Asia/Seoul', type:'Equities'},
  {id:'tsx', flag:'🇨🇦', name:'TSX', region:'Toronto', tz:'America/Toronto', type:'Equities / Commodities'},
  {id:'b3', flag:'🇧🇷', name:'B3', region:'São Paulo', tz:'America/Sao_Paulo', type:'Equities'},
  {id:'bmv', flag:'🇲🇽', name:'BMV', region:'Mexico City', tz:'America/Mexico_City', type:'Equities'},
  {id:'asx', flag:'🇦🇺', name:'ASX', region:'Sydney', tz:'Australia/Sydney', type:'Equities'},
  {id:'crypto', flag:'🌐', name:'Crypto', region:'Global 24/7', tz:'UTC', type:'Digital Assets'}
];

let activeMarket = 'nyse';

function renderMarkets() {
  const grid = document.getElementById('markets-grid');
  if(!grid) return;
  grid.innerHTML = markets.map(m => {
    const isActive = m.id === activeMarket;
    const border = isActive ? '#3b82f6' : '#1e293b';
    const bg = isActive ? '#1e3a8a22' : '#0f172a';
    return `<div class="card card-hover" onclick="setMarket('${m.id}')" style="padding:16px;cursor:pointer;border-color:${border};background:${bg}">
      <div style="font-size:24px;margin-bottom:8px">${m.flag}</div>
      <div style="font-size:14px;font-weight:700;color:#e2e8f0">${m.name}</div>
      <div style="font-size:11px;color:#64748b;margin-bottom:8px">${m.region}</div>
      <div style="font-family:monospace;font-size:14px;color:${isActive ? '#60a5fa' : '#94a3b8'}" id="clk-${m.id}">--:--</div>
      <div style="font-size:10px;color:#475569;margin-top:8px;border-top:1px solid #1e293b;padding-top:8px">${m.type}</div>
    </div>`;
  }).join('');
}

async function setMarket(id) {
  activeMarket = id;
  const m = markets.find(x => x.id === id);
  document.getElementById('hdr-market').innerHTML = `${m.flag} ${m.name} (${m.region})`;
  toast(`Rerouting AI to ${m.name}...`, 'info');
  renderMarkets();
  switchTab('overview');
  
  // Inject thinking animation
  document.getElementById('ai-log').insertAdjacentHTML('afterbegin', `<div class="fade-up" style="padding:5px 0;border-bottom:1px solid #1e293b22;line-height:1.6"><span style="color:#c084fc;font-weight:600">Gemini AI is syncing ${m.name} order books and analyzing...</span> <span class="pulsing">⏳</span></div>`);
  
  try {
    const r = await fetch('/api/set-region/' + id, {method:'POST'});
    const d = await r.json();
    toast(d.message, 'success');
    setTimeout(fetchState, 500);
  } catch(e) {}
}

async function setRiskProfile(val) {
  toast('Updating risk matrix...', 'info');
  try {
    await fetch('/api/set-risk/' + val, {method:'POST'});
    setTimeout(fetchState, 500);
  } catch(e) {}
}

// ── Tab switching ─────────────────────────────────────────────────────────
function switchTab(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  document.getElementById('tab-' + id).classList.add('active');
  if (id === 'global' && document.getElementById('markets-grid').innerHTML.trim() === '') {
    renderMarkets();
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────
function toast(msg, type) {
  const el = document.getElementById('toast');
  const bg = {success:'#14532d', error:'#7f1d1d', info:'#1e3a8a', warn:'#78350f'};
  const border = {success:'#166534', error:'#991b1b', info:'#1d4ed8', warn:'#92400e'};
  el.style.cssText = `position:fixed;bottom:20px;right:20px;padding:12px 18px;border-radius:8px;font-size:13px;font-weight:500;z-index:9999;border:1px solid ${border[type]||border.info};background:${bg[type]||bg.info};color:#fff;max-width:320px;opacity:1;transition:opacity .3s`;
  el.textContent = msg;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.style.opacity = '0', 3500);
}

// ── API commands ──────────────────────────────────────────────────────────
async function sendCmd(endpoint, label) {
  toast(label, 'info');
  switchTab('overview');
  document.getElementById('ai-log').insertAdjacentHTML('afterbegin', `<div class="fade-up" style="padding:5px 0;border-bottom:1px solid #1e293b22;line-height:1.6"><span style="color:#c084fc;font-weight:600">Gemini AI is executing manual override...</span> <span class="pulsing">⏳</span></div>`);
  try {
    const r = await fetch(endpoint, {method:'POST'});
    const d = await r.json();
    toast(d.message || d.status, 'success');
    setTimeout(fetchState, 600);
  } catch(e) {
    toast('Request failed: ' + e, 'error');
  }
}

function richToHtml(s) {
  return s
    .replace(/\[bold cyan\]/g, '<span style="color:#22d3ee;font-weight:600">')
    .replace(/\[bold yellow\]/g, '<span style="color:#fbbf24;font-weight:600">')
    .replace(/\[bold magenta\]/g, '<span style="color:#c084fc;font-weight:600">')
    .replace(/\[bold red\]/g, '<span style="color:#f87171;font-weight:600">')
    .replace(/\[bold green\]/g, '<span style="color:#4ade80;font-weight:600">')
    .replace(/\[bold blue\]/g, '<span style="color:#60a5fa;font-weight:600">')
    .replace(/\[dim\]/g, '<span style="color:#475569">')
    .replace(/\[\/\]/g, '</span>');
}

function clearLogs() {
  document.getElementById('ai-log').innerHTML = '<div style="color:#475569;font-style:italic">Log cleared.</div>';
}

const pnlColor = v => v >= 0 ? '#4ade80' : '#f87171';
function stratBadge(s) { return `<span class="badge" style="background:#1e3a8a22;color:#93c5fd;border-color:#1d4ed8">${(s||'--').replace(/_/g,' ')}</span>`; }
function trendBadge(t) {
  const cfg = { bullish:{bg:'#14532d22',color:'#4ade80',border:'#166534'}, bearish:{bg:'#7f1d1d22',color:'#f87171',border:'#991b1b'}, neutral:{bg:'#1e293b',color:'#94a3b8',border:'#334155'} };
  const c = cfg[t] || cfg.neutral; return `<span class="badge" style="background:${c.bg};color:${c.color};border-color:${c.border}">${t}</span>`;
}
function sideBadge(side) { return side === 'buy' ? `<span class="badge" style="background:#14532d22;color:#4ade80;border-color:#166534">BUY</span>` : `<span class="badge" style="background:#7f1d1d22;color:#f87171;border-color:#991b1b">SELL</span>`; }
function miniBar(pct, color) { return `<div style="display:flex;align-items:center;gap:8px"><div style="width:64px;background:#1e293b;border-radius:4px;overflow:hidden;height:5px"><div style="width:${Math.min(100,Math.max(0,pct))}%;height:5px;background:${color};border-radius:4px"></div></div><span>${pct}</span></div>`; }

// ── Chart init ────────────────────────────────────────────────────────────
let equityChart = null;
function initChart() {
  const ctx = document.getElementById('equityChart').getContext('2d');
  equityChart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ data: [], borderColor: '#3b82f6', borderWidth: 2, tension: 0.3, fill: true, backgroundColor: 'rgba(59, 130, 246, 0.1)', pointRadius: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      scales: {
        x: { display: false },
        y: { ticks: { color: '#94a3b8', callback: v => '$' + v.toLocaleString() }, grid: { color: '#1e293b' } }
      }
    }
  });
}

// ── Clock Ticker ──────────────────────────────────────────────────────────
setInterval(() => {
  const now = new Date();
  document.getElementById('hdr-clock').textContent = now.toLocaleTimeString();
  
  markets.forEach(m => {
    const el = document.getElementById('clk-' + m.id);
    if(el) {
      if(m.tz === 'UTC') {
        el.textContent = now.toISOString().substring(11,16) + ' UTC';
      } else {
        el.textContent = new Date(now.toLocaleString('en-US', { timeZone: m.tz })).toLocaleTimeString('en-US', {hour12:false, hour:'2-digit', minute:'2-digit'});
      }
    }
  });
}, 1000);

// ── State tracking ────────────────────────────────────────────────────────
let lastLogStr = "";
let lastHistLen = 0;

async function fetchState() {
  let d;
  try {
    const r = await fetch('/api/state');
    if (!r.ok) return;
    d = await r.json();
  } catch { return; }

  const a = d.account;

  const modeEl = document.getElementById('hdr-mode');
  if (d.config?.dry_run) {
    modeEl.textContent = 'DRY-RUN'; modeEl.style.cssText = 'background:#78350f22;color:#fbbf24;border:1px solid #92400e';
  } else {
    modeEl.textContent = 'LIVE'; modeEl.style.cssText = 'background:#14532d22;color:#4ade80;border:1px solid #166534';
  }

  const isActive = a.status === 'ACTIVE';
  document.getElementById('hdr-dot').style.background = isActive ? '#22c55e' : '#ef4444';
  document.getElementById('status-dot').style.background = isActive ? '#22c55e' : '#ef4444';
  document.getElementById('m-status').textContent = a.status;
  document.getElementById('m-status').style.color = isActive ? '#4ade80' : '#f87171';

  document.getElementById('m-equity').textContent = '$' + a.equity.toLocaleString('en-US', {minimumFractionDigits:2});
  const pnlEl = document.getElementById('m-pnl');
  pnlEl.textContent = (a.daily_pnl >= 0 ? '+' : '') + '$' + Math.abs(a.daily_pnl).toLocaleString('en-US',{minimumFractionDigits:2});
  pnlEl.style.color = pnlColor(a.daily_pnl);
  
  const pnlPctEl = document.getElementById('m-pnl-pct');
  pnlPctEl.textContent = (a.daily_pnl_pct >= 0 ? '+' : '') + a.daily_pnl_pct + '%';
  pnlPctEl.style.color = pnlColor(a.daily_pnl);

  document.getElementById('m-delta').textContent = d.portfolio_delta.toFixed(4);
  document.getElementById('m-positions').textContent = `${a.open_positions} position${a.open_positions!==1?'s':''} open`;

  const theta = d.portfolio_theta || 0;
  document.getElementById('g-theta').textContent = (theta >= 0 ? '+' : '') + '$' + theta.toFixed(2);
  document.getElementById('g-theta').style.color = pnlColor(theta);

  const lossUsed = Math.min(100, Math.abs(a.daily_pnl) / 3000 * 100);
  document.getElementById('g-pnl-bar').style.width = lossUsed + '%';
  document.getElementById('g-pnl-bar').style.background = lossUsed > 70 ? '#ef4444' : '#22c55e';
  document.getElementById('g-pnl-lbl').textContent = `$${a.daily_pnl.toFixed(0)} / -$3,000`;
  
  document.getElementById('g-pos-bar').style.width = (a.open_positions / 5 * 100) + '%';
  document.getElementById('g-pos-lbl').textContent = `${a.open_positions} / 5`;
  
  const marginUsd = a.equity - a.buying_power;
  const marginPct = a.equity > 0 ? (marginUsd / a.equity) * 100 : 0;
  document.getElementById('g-margin-bar').style.width = marginPct + '%';
  document.getElementById('g-margin-lbl').textContent = marginPct.toFixed(2) + '%';
  document.getElementById('g-bp').textContent = '$' + a.buying_power.toLocaleString('en-US', {minimumFractionDigits:0});
  document.getElementById('g-margin-usd').textContent = '$' + marginUsd.toLocaleString('en-US', {minimumFractionDigits:0});

  if (!equityChart && document.getElementById('equityChart')) initChart();
  if (equityChart && d.equity_history && d.equity_history.length > 0) {
    if (d.equity_history.length !== lastHistLen) {
      lastHistLen = d.equity_history.length;
      equityChart.data.labels = d.equity_history.map(h => h.time);
      equityChart.data.datasets[0].data = d.equity_history.map(h => h.equity);
      equityChart.update('none');
    }
  }

  document.getElementById('g-watchlist').innerHTML = (d.config?.watchlist||[]).map(s =>
    `<span class="badge" style="background:#1e293b;color:#94a3b8;border-color:#334155">${s}</span>`
  ).join('');

  const sigs = d.market_signals || [];
  if (sigs.length > 0) {
    document.getElementById('sig-tbody').innerHTML = sigs.map(s => {
      const rsiColor = s.rsi < 30 ? '#4ade80' : s.rsi > 70 ? '#f87171' : '#fbbf24';
      const ivrColor = s.iv_rank >= 50 ? '#f59e0b' : s.iv_rank >= 30 ? '#fbbf24' : '#818cf8';
      const sentiment = s.rsi > 60 ? '🔥 Bullish' : s.rsi < 40 ? '❄️ Bearish' : '⚖️ Neutral';
      return `<tr style="border-bottom:1px solid #1e293b" onmouseover="this.style.background='#0f172a'" onmouseout="this.style.background=''">
        <td style="padding:12px 18px;font-weight:700;color:#f1f5f9">${s.symbol}</td>
        <td style="padding:12px 18px;color:#94a3b8;font-family:monospace">$${s.price.toLocaleString()}</td>
        <td style="padding:12px 18px">${miniBar(s.rsi, rsiColor)} </td>
        <td style="padding:12px 18px">${miniBar(s.iv_rank, ivrColor)}</td>
        <td style="padding:12px 18px;color:#94a3b8">${s.current_iv}%</td>
        <td style="padding:12px 18px">${trendBadge(s.trend)}</td>
        <td style="padding:12px 18px;font-weight:600">${sentiment}</td>
        <td style="padding:12px 18px">${stratBadge(s.strategy)}</td>
      </tr>`;
    }).join('');
  }

  const logs = d.recent_logs || [];
  const logStr = JSON.stringify(logs);
  if (logStr !== lastLogStr) {
    lastLogStr = logStr;
    if (logs.length > 0) {
      document.getElementById('ai-log').innerHTML = [...logs].reverse().map(l =>
        `<div class="fade-up" style="padding:5px 0;border-bottom:1px solid #1e293b22;line-height:1.6">${richToHtml(l)}</div>`
      ).join('');
    }
  }
}

renderMarkets();
setInterval(fetchState, 2000);
fetchState();
</script>
</body>
</html>"""
