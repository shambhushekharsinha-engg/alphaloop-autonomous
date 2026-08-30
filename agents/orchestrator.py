"""
agents/orchestrator.py

Orchestrator Agent — production-hardened version.
==================================================
Key fixes:
  - Execution agent is now optional (graceful fallback to dry-run mode)
  - Scanner runs even if execution fails
  - Decision cycle waits for at least one signal before acting
  - All exceptions are caught and logged, never crash the loop
  - Exposes force_scan() and force_cycle() for web API integration
"""
import asyncio
from typing import Optional

from core.config import config
from core.logger import get_logger
from core.state import AgentState
from agents.market_scanner import MarketScannerAgent
from agents.strategy_selector import StrategySelectorAgent
from agents.risk_guardian import RiskGuardianAgent
from agents.execution_agent import ExecutionAgent

logger = get_logger(__name__, agent="Orchestrator")


class OrchestratorAgent:
    def __init__(self):
        self.state = AgentState()
        self.scanner = MarketScannerAgent(self.state)
        self.selector = StrategySelectorAgent(self.state)
        self.risk_guardian = RiskGuardianAgent(self.state)
        self._exec_agent: Optional[ExecutionAgent] = None
        self._running = False

    async def run(self):
        """
        Main agent loop. Starts all background tasks and runs the decision
        cycle in a fault-tolerant loop. Never crashes — all errors are caught.
        """
        self._running = True
        logger.info("AlphaLoop Orchestrator starting up...")
        await self.state.add_log("🚀 [bold blue]AlphaLoop Autonomous starting up...[/]")

        # Start scanner and risk monitor as independent background tasks
        # These will keep running even if the execution agent fails
        asyncio.create_task(self._run_scanner_loop())
        asyncio.create_task(self._run_risk_monitor_loop())

        # Start the execution agent (with graceful fallback to dry-run)
        await self._start_execution_agent()

        # Main decision loop
        cycle_count = 0
        while self._running:
            if self.state.trading_halted:
                await asyncio.sleep(30)
                continue

            # Wait for at least one signal before making any decisions
            if not self.state.signals:
                await asyncio.sleep(5)
                continue

            cycle_count += 1
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Unhandled error in decision cycle {cycle_count}: {e}", exc_info=True)
                await self.state.add_log(f"⚠️ [bold red]Cycle error:[/] {str(e)[:80]}")

            await asyncio.sleep(120)  # Wait 2 minutes between decision cycles

    async def _start_execution_agent(self):
        """Start MCP execution agent, fall back to dry-run if MCP unavailable."""
        exec_agent = ExecutionAgent(self.state)
        try:
            await exec_agent.__aenter__()
            self._exec_agent = exec_agent
            # Sync account state on startup
            await exec_agent.sync_account()
            await exec_agent.sync_positions()
            await self.state.add_log("✅ [bold green]Alpaca MCP connected. Live trading enabled.[/]")
            logger.info("ExecutionAgent connected via MCP")
        except Exception as e:
            logger.warning(f"MCP connection failed ({e}) — switching to DRY-RUN mode")
            await self.state.add_log(f"⚠️ [bold yellow]MCP unavailable — running in DRY-RUN mode[/]")
            # Force dry-run mode
            config.dry_run = True
            exec_agent_dry = ExecutionAgent(self.state)
            await exec_agent_dry.__aenter__()
            self._exec_agent = exec_agent_dry

    async def _run_scanner_loop(self):
        """Wrapper to run the scanner and log any errors."""
        while self._running:
            try:
                await self.scanner._scan_all()
                await self.state.add_log("📡 [bold cyan]Market scan completed.[/]")
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await self.state.add_log(f"⚠️ [bold red]Scanner error:[/] {str(e)[:80]}")
            await asyncio.sleep(config.scanner.scan_interval_seconds)

    async def _run_risk_monitor_loop(self):
        """Wrapper to run the risk monitor loop with auto-close support."""
        while self._running:
            await asyncio.sleep(60)
            try:
                positions_to_close = await self._check_exit_conditions()
                for symbol in positions_to_close:
                    if self._exec_agent:
                        await self._exec_agent.close_position(symbol)
            except Exception as e:
                logger.error(f"Risk monitor error: {e}")

    async def _check_exit_conditions(self):
        """Check all positions for stop-loss or take-profit breaches."""
        positions_to_close = []
        tp_pct = 0.50
        sl_pct = config.risk.position_stop_loss_pct

        async with self.state._lock:
            for symbol, pos in self.state.positions.items():
                if pos.avg_entry_price <= 0 or pos.current_price <= 0:
                    continue

                if pos.side == "buy":
                    profit_pct = (pos.current_price - pos.avg_entry_price) / pos.avg_entry_price
                    loss_pct = -profit_pct
                else:
                    profit_pct = (pos.avg_entry_price - pos.current_price) / max(pos.avg_entry_price, 0.01)
                    loss_pct = -profit_pct

                if loss_pct > sl_pct:
                    logger.warning(f"Stop-loss triggered for {symbol}: loss={loss_pct:.1%}")
                    positions_to_close.append(symbol)
                    self.state.recent_logs.append(
                        f"🛑 [bold red]STOP-LOSS:[/] {symbol} at {loss_pct:.1%} loss — closing"
                    )
                elif profit_pct > tp_pct:
                    logger.info(f"Take-profit triggered for {symbol}: profit={profit_pct:.1%}")
                    positions_to_close.append(symbol)
                    self.state.recent_logs.append(
                        f"🎯 [bold green]TAKE-PROFIT:[/] {symbol} locked {profit_pct:.1%} — closing"
                    )

        return positions_to_close

    async def _run_cycle(self):
        """One full decision cycle: sync → select → risk check → execute."""
        logger.info("Starting decision cycle...")

        # Sync account state
        if self._exec_agent:
            await self._exec_agent.sync_account()
            await self._exec_agent.sync_positions()

        # Select best opportunity
        proposal = await self.selector.select_best_opportunity()
        if not proposal:
            await self.state.add_log("🔍 [dim]No actionable opportunity found this cycle.[/]")
            return

        # Evaluate risk
        decision = await self.risk_guardian.evaluate(proposal.order, proposal.estimated_cost)
        if not decision.allowed:
            logger.info(f"Order rejected: {decision.reason}")
            await self.state.add_log(f"🚫 [bold red]Risk gate:[/] {decision.reason}")
            return

        # Execute
        if self._exec_agent:
            success = await self._exec_agent.submit_order(proposal.order)
            if success:
                strategy_name = type(proposal.order).__name__
                await self.state.add_log(
                    f"✅ [bold green]EXECUTED:[/] {strategy_name} on {proposal.signal.symbol}"
                )
            else:
                await self.state.add_log(
                    f"❌ [bold red]EXECUTION FAILED:[/] {proposal.signal.symbol}"
                )

    async def force_scan(self):
        """Trigger an immediate market scan (used by web API)."""
        await self.state.add_log("⚡ [bold yellow]Manual scan triggered from Web UI[/]")
        try:
            await self.scanner._scan_all()
            await self.state.add_log("📡 [bold cyan]Manual scan completed.[/]")
        except Exception as e:
            await self.state.add_log(f"⚠️ [bold red]Scan failed:[/] {str(e)[:80]}")
        # Run one decision cycle right after the scan
        try:
            await self._run_cycle()
        except Exception as e:
            await self.state.add_log(f"⚠️ [bold red]Cycle error:[/] {str(e)[:80]}")
