# AlphaLoop Autonomous — Multi-Agent Options Trader

AlphaLoop Autonomous is an advanced options trading system built on Alpaca. It uses a **multi-agent architecture** (Market Scanner, Strategy Selector, Risk Guardian, Execution Agent) coordinated by a Gemini LLM Orchestrator to autonomously deploy sophisticated options strategies (Iron Condors, Credit Spreads).

## Core Innovations
- **Agentic Decision Making**: Gemini dynamically reasons through market data to pick the optimal strategy based on RSI and IV Rank.
- **IV Rank Signal Engine**: Real-time options chains analyzed to calculate IV percentiles.
- **Hard Risk Gates**: Dedicated Risk Guardian prevents account blowups (5% sizing limit, 3% daily loss limit).
- **MCP-First Execution**: All trading happens through the official `alpaca-mcp-server`.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment Variables:**
   ```bash
   cp .env.example .env
   # Fill in APCA_API_KEY_ID, APCA_API_SECRET_KEY, and GEMINI_API_KEY
   ```
3. **Run the system:**
   ```bash
   python agent.py
   ```
   (You will see a live rich terminal dashboard!)

## Testing
Run unit tests with pytest:
```bash
pytest tests/
```
