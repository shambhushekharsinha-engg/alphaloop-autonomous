<div align="center">
  <img src="https://img.shields.io/badge/AlphaLoop-Autonomous-60a5fa?style=for-the-badge&logo=rocket" alt="AlphaLoop Banner"/>
  <h1>AlphaLoop Autonomous 🧠📈</h1>
  <p><em>An autonomous, multi-agent AI options trading system powered by Gemini 3.6 Flash and Alpaca MCP.</em></p>

  [![Live Demo](https://img.shields.io/badge/🔴_Live_Demo-alphaloop--autonomous.vercel.app-c084fc?style=for-the-badge)](https://alphaloop-autonomous.vercel.app/)
  [![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
</div>

<hr>

## 🚀 The Vision
Trading options requires analyzing Greeks, Volatility (IV), and Technicals (RSI) simultaneously—a task uniquely suited for autonomous AI. **AlphaLoop** replaces manual trading with a swarm of specialized AI sub-agents. It scans 20 global markets, calculates Risk/Reward, and securely executes complex multi-leg strategies (Iron Condors, Credit Spreads) via the Model Context Protocol (MCP).

---

## ✨ Killer Features
- **🤖 LLM Orchestration:** Powered by Google's `gemini-3.6-flash`, the orchestrator dynamically reasons through live market signals to select the optimal trading strategy.
- **🌍 Global Market Routing:** Seamlessly switches between 20 major world markets (NYSE, TSE, Crypto, LSE) adjusting active watchlists and timezones in real-time.
- **🛡️ Risk Guardian Engine:** A hard-coded, zero-trust risk subagent that blocks any LLM hallucination that breaches maximum portfolio delta, margin utilization, or daily loss limits.
- **⚡ MCP Execution:** The industry's first autonomous trader to execute complex orders entirely through the official `alpaca-mcp-server`.
- **📊 Live Streaming Dashboard:** A beautiful, dark-mode dashboard (built with Tailwind & Chart.js) visualizing the AI's internal logic, portfolio theta, and live equity curve.

---

## 🧠 System Architecture

AlphaLoop utilizes a strict Multi-Agent lifecycle to guarantee safe trading execution:

```mermaid
graph TD;
    A[📡 Market Scanner] -->|Calculates RSI & IV Rank| B(🧠 Strategy Selector);
    B -->|Proposes Trade via Gemini 3.6| C{🛡️ Risk Guardian};
    C -->|Rejects| D[Log: Risk Breach];
    C -->|Approves| E[⚡ Execution Agent];
    E -->|Routes Order via MCP| F[(Alpaca API)];
```

---

## 💻 Quick Start (Local Backend)

Want to run the full Python orchestration engine locally?

1. **Clone & Install**
   ```bash
   git clone https://github.com/shambhushekharsinha-engg/alphaloop-autonomous.git
   cd alphaloop-autonomous
   pip install -r requirements.txt
   pip install uv
   ```

2. **Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   APCA_API_KEY_ID=your_alpaca_key
   APCA_API_SECRET_KEY=your_alpaca_secret
   GEMINI_API_KEY=your_google_ai_key
   ```

3. **Ignite the Orchestrator**
   ```bash
   python web.py
   ```
   *Navigate to `http://localhost:8080` to view the live trading matrix.*

---

## ☁️ Cloud Deployment (Vercel / Render)

### The Frontend (Static Mock)
For hackathon demonstration purposes, the frontend is decoupled and deployed instantly on Vercel. This simulates the backend data engine to guarantee 100% uptime for judges.
👉 **[View the Live Vercel Deployment](https://alphaloop-autonomous.vercel.app/)**

### The Backend (Docker)
We include a production-ready `Dockerfile`. You can deploy the active Python trading engine to platforms like **Render**, **Railway**, or **Hugging Face Spaces**.
```bash
docker build -t alphaloop .
docker run -p 8080:8080 --env-file .env alphaloop
```

---

<div align="center">
  <i>⚠️ <b>Disclaimer:</b> AlphaLoop is built for educational and hackathon purposes. Do not use this to trade real money without extensive paper-trading validation.</i>
</div>
