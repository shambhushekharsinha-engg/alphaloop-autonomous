# AlphaLoop: Autonomous Neural Options Trader
## 2-Minute Demo Video Script

**[0:00 - 0:10] Visual: Start on the main Dashboard Overview. The "Live Equity Curve" and "Active Options Portfolio" are visible.**
*Audio:* "Welcome to AlphaLoop. This isn't just an options screener—it's a fully autonomous AI hedge fund manager built for the Alpaca hackathon. Today, I'll show you how our multi-agent architecture uses Gemini to actively scan, reason, and trade options entirely on its own."

**[0:10 - 0:25] Visual: Click on the "Controls" tab. Click the "Force Market Scan" button.**
*Audio:* "It all starts with the Market Scanner. Every cycle, it pulls live market data across multiple symbols, calculating RSI, IV Rank, and price action to hunt for volatility mispricings."

**[0:25 - 0:45] Visual: Click over to the "Signals" tab. Hover over the new "AI Reasoning" column to show Gemini's text.**
*Audio:* "Once a signal is generated, it's passed to our Strategy Selector agent, which is powered by Google's Gemini 3.6 Flash. This is where the magic happens. Look at the AI Reasoning column: Gemini isn't just guessing. It actually reads the RSI and IV metrics in real-time, formulates a thesis—like recognizing an oversold condition with high IV—and decides to construct a Bull Put Spread to collect premium."

**[0:45 - 1:05] Visual: Click on the "Settings" tab, showing the Risk Guardian limits (Max Position %, Max Portfolio Delta, Daily Loss Limit).**
*Audio:* "But before any order goes out, it must pass the Risk Guardian. This is a deterministic Python agent that acts as an impassable firewall. If an AI trade exceeds our maximum portfolio delta of 0.20 or violates a daily loss limit, the Risk Guardian outright rejects the trade. AI proposes, code decides."

**[1:05 - 1:30] Visual: Show the "History" tab to show the placed order. Then switch tabs in your browser to the actual Alpaca Dashboard (alpaca.markets) showing the paper trade successfully executed.**
*Audio:* "When a trade is approved, our Execution Agent takes over. Using the Model Context Protocol, it constructs a complex multi-leg options order—calculating strikes, expirations, and limit prices on the fly—and sends it directly to Alpaca. As you can see right here in our live Alpaca paper trading dashboard, the multi-leg order has successfully landed."

**[1:30 - 1:50] Visual: Switch back to the Vercel dashboard. Show the "Global Markets" and scrolling Dark Pool Tracker.**
*Audio:* "The entire pipeline—from scanning, to LLM reasoning, to risk management, to live Alpaca execution—happens completely autonomously. We've wrapped the whole system in this Bloomberg-style terminal for deep observability."

**[1:50 - 2:00] Visual: Zoom out to full screen on the dashboard.**
*Audio:* "AlphaLoop proves that by combining the logical reasoning of Gemini with the strict deterministic constraints of a Risk Engine, we can safely let AI execute advanced derivatives trading. Thanks for watching."
