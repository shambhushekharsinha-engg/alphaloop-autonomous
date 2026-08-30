# Options Alpha Agents: Hackathon Write-up

## 1. AI Logic & Trading Strategy
The **AlphaLoop Autonomous System** utilizes a state-of-the-art multi-agent architecture coordinated by a Gemini-powered LLM orchestrator. 

- **The Market Scanner Agent** continuous polls OHLCV bars and options chains to compute Wilder's RSI, 9/21 EMA trend crossovers, and an options-specific **IV Rank (IVR)**.
- **The Strategy Selector Agent** takes this data and uses Gemini function-calling to choose an options strategy. It dynamically shifts between:
  - **Iron Condors**: Deployed when IV Rank > 50 (rich premium) and trend is neutral.
  - **Credit Spreads (Bull Put / Bear Call)**: Deployed on RSI extremes when IV Rank is elevated.
  - **Protective Puts**: Deployed when IV Rank is low (<30) as cheap portfolio hedges.

## 2. Risk Gates
A standalone **Risk Guardian Agent** evaluates every proposed trade before execution, acting as an impassable firewall:
1. **$100k Balance Gate**: Ensures the system is running in a compliant hackathon account.
2. **Maximum Position Sizing**: A single trade's cost (or max loss) cannot exceed 5% of account equity.
3. **Portfolio Delta Limits**: Blocks trades that would push the total portfolio net delta beyond ±0.20 (enforcing market-neutrality).
4. **Daily Loss Halt**: Automatically halts all new trading if daily P&L drops below -3% of the starting balance.
5. **Continuous Stop-Loss Monitor**: A background async loop automatically exits any position that suffers a >30% drawdown on premium.

## 3. Alpaca Infrastructure Implementation
This project deeply integrates Alpaca's ecosystem, specifically leveraging the **Model Context Protocol (MCP)**:
- **MCP-First Execution**: The Execution Agent is an MCP client. It spawns the official `alpaca-mcp-server` via `uvx` and uses standardized MCP tools (`place_order`, `get_positions`, `close_position`) to manage the portfolio. This completely abstracts raw REST execution.
- **Alpaca-Py Data**: The Market Scanner uses `alpaca-py`'s `OptionHistoricalDataClient` to fetch live options Greeks and Implied Volatilities, enabling the advanced IV Rank logic.
- **Environment**: The entire 4-agent system is designed for the paper-trading environment, safely simulating multi-leg options flow with zero real capital risk.
