<div align="center">
  <img src="assets/alphaloop_cover.jpg" alt="AlphaLoop Cover" width="100%"/>

  <h1>🧠 AlphaLoop — Autonomous Neural Options Trader 📈</h1>
  <p><em>An autonomous, multi-agent AI options trading system powered by Gemini 3.6 Flash and Alpaca MCP.</em></p>

  <a href="https://www.youtube.com/watch?v=EN-QTGJFPms"><img src="https://img.shields.io/badge/Watch_Demo-YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube Demo"/></a>
  <a href="https://alphaloop-autonomous.vercel.app/"><img src="https://img.shields.io/badge/Live_Dashboard-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Vercel"/></a>
  <a href="https://alphaloop-autonomous.onrender.com/api/state"><img src="https://img.shields.io/badge/Live_AI_Backend-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Render"/></a>
  <a href="https://github.com/shambhushekharsinha-engg/alphaloop-autonomous"><img src="https://img.shields.io/badge/Source_Code-GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"/></a>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Gemini_3.6_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini"/>
  <img src="https://img.shields.io/badge/Alpaca_MCP-00C805?style=for-the-badge" alt="Alpaca MCP"/>
</div>

<br>

> [!IMPORTANT]
> **JUDGES — HOW TO TEST THIS LIVE PROJECT**
>
> | URL | Purpose |
> |-----|---------|
> | 🖥️ [alphaloop-autonomous.vercel.app](https://alphaloop-autonomous.vercel.app) | **Frontend Dashboard** — Click "Force Market Scan" here to trigger the AI |
> | 🤖 [alphaloop-autonomous.onrender.com/api/state](https://alphaloop-autonomous.onrender.com/api/state) | **Live AI Backend** — See raw JSON from the running agent |
> | ❤️ [alphaloop-autonomous.onrender.com/api/health](https://alphaloop-autonomous.onrender.com/api/health) | **Health Check** — Verify Gemini + Alpaca connectivity status |
> | 📹 [youtube.com/watch?v=EN-QTGJFPms](https://www.youtube.com/watch?v=EN-QTGJFPms) | **Demo Video** — Full walkthrough of a live trading cycle |

---

## 🎬 Demo Video

[![AlphaLoop Demo Video](https://img.youtube.com/vi/EN-QTGJFPms/maxresdefault.jpg)](https://www.youtube.com/watch?v=EN-QTGJFPms)
*Click to watch — See Gemini reasoning live, Risk Guardian blocking bad trades, and orders landing in Alpaca.*

---

## 💡 The Vision

Trading options requires simultaneously analyzing Greeks, Volatility (IV), and Technicals (RSI) — a task uniquely suited for autonomous AI. **AlphaLoop** replaces the manual analysis loop with a swarm of specialized AI sub-agents that:

- 📊 **Scan** 20 global markets for volatility mispricings
- 🧠 **Reason** about each signal using Google Gemini in natural language  
- 🛡️ **Guard** against bad trades with a deterministic Python risk engine
- ⚡ **Execute** complex multi-leg options orders directly via Alpaca MCP

---

## ⚙️ System Architecture

```mermaid
graph TD;
    A["📊 Market Scanner<br/>RSI · IV Rank · Trend"] -->|"Signals"| B["🧠 Strategy Selector<br/>Gemini 3.6 Flash"];
    B -->|"Proposes Trade + Rationale"| C{"🛡️ Risk Guardian<br/>Delta · Size · Loss Limits"};
    C -->|"REJECTED"| D["📝 Log: Risk Breach"];
    C -->|"APPROVED"| E["⚡ Execution Agent<br/>MCP Tool Calls"];
    E -->|"Multi-leg Order"| F[("🏦 Alpaca API<br/>Paper / Live")];
```

---

## 🚀 Feature Showcase

### 1. 🧠 LLM Orchestration — Visible AI Reasoning
Powered by `gemini-3.6-flash`. The AI reads live RSI and IV Rank values and formulates a financial thesis in plain English. **You can see exactly why it picks each trade — no black box.**

<img src="assets/02_ai_reasoning_signals.png" width="100%" alt="AI Reasoning in Signals Tab"/>

---

### 2. 🛡️ Risk Guardian — The Deterministic Firewall
A zero-trust Python agent that blocks any trade that violates the hardcoded safety rules. AI proposes — code decides.

| Guard | Limit |
|-------|-------|
| Max Portfolio Delta | 0.20 |
| Max Single Position Size | 5% of buying power |
| Daily Loss Cap | 3% |

<img src="assets/04_risk_guardian_settings.png" width="100%" alt="Risk Guardian Settings"/>

---

### 3. 🌐 Global Market Routing + Dark Pool Tracker

<img src="assets/08_dark_pool_tracker.png" width="100%" alt="Dark Pool Tracker and Global Markets"/>

Seamlessly switches between **20 world markets** (NYSE, TSE, Crypto, LSE). Includes a scrolling Dark Pool block-trade tracker for institutional flow monitoring.

---

### 4. ⚡ Alpaca MCP Execution — Live Proof

<img src="assets/09_alpaca_live_execution.png" width="100%" alt="Alpaca Live Execution"/>

The first autonomous trader to use the **official `alpaca-mcp-server`** for complex multi-leg options execution. Strike calculations, expiration selection, and order routing happen inside the AI.

---

### 5. 📊 Full Dashboard Overview

<img src="assets/01_dashboard_overview.png" width="100%" alt="Full Dashboard Overview"/>

---

## 🛠️ Quick Start (Run Locally)

```bash
# 1. Clone the repo
git clone https://github.com/shambhushekharsinha-engg/alphaloop-autonomous.git
cd alphaloop-autonomous

# 2. Install dependencies
pip install -r requirements.txt
pip install uv

# 3. Create .env with your API keys
echo "APCA_API_KEY_ID=your_alpaca_key" >> .env
echo "APCA_API_SECRET_KEY=your_alpaca_secret" >> .env
echo "GEMINI_API_KEY=your_google_ai_key" >> .env
echo "DRY_RUN=false" >> .env

# 4. Launch the orchestrator
python web.py
# Navigate to http://localhost:8080
```

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Reasoning | Google Gemini 3.6 Flash |
| Broker Integration | Alpaca API via MCP |
| Backend | Python 3.11 · FastAPI · AsyncIO |
| Frontend | HTML · JavaScript · Chart.js |
| Cloud (AI Backend) | Render |
| Cloud (Dashboard) | Vercel |

---

<div align="center">
  <b>Built by Shambhu Shekhar Sinha · Greater Noida Institute of Technology</b><br/>
  <i>Alpaca AI Trading Agents Hackathon · Lablab.ai · 2026</i><br/><br/>
  <i>⚠️ AlphaLoop is built for educational and hackathon purposes. Do not use with real money without extensive paper-trading validation.</i>
</div>
