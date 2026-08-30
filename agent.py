"""
agent.py

Entry point for AlphaLoop Autonomous Options Trading System.
"""
import asyncio
import logging
from core.config import config
from agents.orchestrator import OrchestratorAgent
from dashboard.dashboard import AlphaDashboard

async def main():
    config.validate()

    orchestrator = OrchestratorAgent()
    dashboard = AlphaDashboard(orchestrator.state)

    # Run orchestrator and dashboard concurrently
    await asyncio.gather(
        orchestrator.run(),
        dashboard.run()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAlphaLoop shutdown requested. Exiting cleanly.")
