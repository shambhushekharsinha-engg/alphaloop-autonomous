"""
agents/execution_agent.py

Execution Agent (MCP Client)
=============================
Responsible for all ORDER PLACEMENT and POSITION MANAGEMENT via the
official Alpaca MCP Server. This is the ONLY module that talks to the broker.

Architecture:
  - Spawns `alpaca-mcp-server` as a subprocess via uvx (stdio transport)
  - Uses the MCP Python SDK ClientSession to call tools
  - All trades go through here — no raw REST calls for order placement

MCP Tools used:
  - get_account           → fetch equity, buying power
  - get_positions         → list current holdings
  - place_order           → submit options orders (market/limit)
  - close_position        → exit an open position
  - cancel_order          → cancel a pending order
  - get_orders            → list recent orders for dashboard
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Union

from core.config import config
from core.logger import get_logger
from core.state import AgentState, OptionPosition
from strategies.iron_condor import IronCondorOrder, OptionLeg
from strategies.credit_spread import CreditSpreadOrder
from strategies.protective_put import ProtectivePutOrder

logger = get_logger(__name__, agent="ExecutionAgent")

AnyOrder = Union[IronCondorOrder, CreditSpreadOrder, ProtectivePutOrder]

# ── Optional MCP imports ─────────────────────────────────────────────────────
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("mcp package not installed — execution agent will run in dry-run mode")


class ExecutionAgent:
    """
    Manages the lifecycle of the MCP server connection and executes all trades.
    Designed to be used as an async context manager:

        async with ExecutionAgent(state) as agent:
            await agent.sync_account()
            await agent.submit_order(iron_condor_order)
    """

    def __init__(self, state: AgentState):
        self.state = state
        self.dry_run = config.dry_run or not MCP_AVAILABLE
        self._session: Optional[Any] = None
        self._cm_stack = []

    async def __aenter__(self):
        if not self.dry_run:
            await self._start_mcp_server()
        else:
            logger.info("Execution Agent in DRY-RUN mode — no orders will be placed")
        return self

    async def __aexit__(self, *args):
        for cm in reversed(self._cm_stack):
            await cm.__aexit__(*args)

    # ── MCP Server Lifecycle ────────────────────────────────────────────────

    async def _start_mcp_server(self):
        import shutil
        uvx_cmd = shutil.which("uvx")
        if not uvx_cmd:
            raise FileNotFoundError(
                "Could not find 'uvx'. Please install it by running `pip install uv` "
                "and ensure it is in your PATH."
            )

        server_params = StdioServerParameters(
            command=uvx_cmd,
            args=["alpaca-mcp-server"],
            env={
                "ALPACA_API_KEY": config.alpaca.api_key,
                "ALPACA_SECRET_KEY": config.alpaca.api_secret,
                "PATH": os.environ.get("PATH", ""),
            },
        )
        logger.info(f"Starting Alpaca MCP Server via {uvx_cmd}...")
        stdio_cm = stdio_client(server_params)
        read, write = await stdio_cm.__aenter__()
        self._cm_stack.append(stdio_cm)

        session_cm = ClientSession(read, write)
        self._session = await session_cm.__aenter__()
        self._cm_stack.append(session_cm)

        await self._session.initialize()
        logger.info("Connected to Alpaca MCP Server")

        # Enumerate available tools for diagnostics
        tools_result = await self._session.list_tools()
        tool_names = [t.name for t in tools_result.tools]
        logger.info(f"MCP tools available: {tool_names}")

    async def _call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict:
        """Call an MCP tool and parse the JSON response."""
        if self.dry_run or not self._session:
            logger.info(f"[DRY-RUN] Would call MCP tool: {tool_name}", extra={"args": arguments})
            return {}
        result = await self._session.call_tool(tool_name, arguments=arguments)
        if result.content:
            raw = result.content[0].text
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
        return {}

    # ── Account Sync ────────────────────────────────────────────────────────

    async def sync_account(self) -> bool:
        """Fetch account equity/buying power and update shared state."""
        data = await self._call("get_account", {})
        if not data:
            logger.warning("Could not fetch account — running with cached state")
            return False

        equity = float(data.get("equity", self.state.equity))
        buying_power = float(data.get("buying_power", self.state.buying_power))

        # Hackathon rule: warn if balance looks wrong
        if equity < 50_000:
            logger.warning(
                f"Account equity ${equity:,.2f} is far below required $100,000 starting balance!"
            )

        await self.state.update_account(equity, buying_power)
        logger.info(f"Account synced: equity=${equity:,.2f}, BP=${buying_power:,.2f}")
        return True

    async def sync_positions(self):
        """Refresh the positions in shared state from the broker."""
        data = await self._call("get_positions", {})
        if not data:
            return
        # data may be a list of position objects
        positions = data if isinstance(data, list) else data.get("positions", [])
        for pos_data in positions:
            symbol = pos_data.get("symbol", "")
            if not symbol:
                continue
            qty = int(pos_data.get("qty", 1))
            avg_price = float(pos_data.get("avg_entry_price", 0))
            current_price = float(pos_data.get("current_price", avg_price))
            unrealized_pnl = float(pos_data.get("unrealized_pl", 0))

            pos = OptionPosition(
                symbol=symbol,
                underlying=symbol[:3],  # Rough guess; refine with full OCC parse
                strategy="unknown",
                side="buy" if qty > 0 else "sell",
                qty=abs(qty),
                avg_entry_price=avg_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
            )
            await self.state.add_position(pos)

    # ── Order Submission ────────────────────────────────────────────────────

    async def submit_order(self, order: AnyOrder) -> bool:
        """
        Submit all legs of a multi-leg options order.

        For Iron Condors (4 legs), we submit legs in pairs to minimize slippage:
          - Short put spread first, then short call spread
        For 2-leg spreads and single legs, submit all at once.

        Returns True if all legs placed successfully.
        """
        strategy_name = type(order).__name__
        logger.info(
            f"Submitting {strategy_name} on {order.underlying}",
            extra={"legs": len(order.legs), "group_id": order.group_id}
        )

        success_count = 0
        for leg in order.legs:
            placed = await self._place_option_leg(leg)
            if placed:
                success_count += 1
                pos = OptionPosition(
                    symbol=leg.symbol,
                    underlying=leg.underlying,
                    strategy=strategy_name.lower(),
                    side=leg.side,
                    qty=leg.qty,
                    avg_entry_price=0.0,  # Filled by broker; updated on next sync
                    stop_loss_price=0.0,
                    group_id=order.group_id,
                )
                await self.state.add_position(pos)
            else:
                logger.error(f"Failed to place leg: {leg.symbol}")

        if success_count == len(order.legs):
            await self.state.log_order({
                "time": str(date.today()),
                "strategy": strategy_name,
                "underlying": order.underlying,
                "legs": success_count,
                "group_id": order.group_id,
                "status": "FILLED",
            })
            logger.info(f"{strategy_name} fully placed ({success_count} legs)")
            return True
        else:
            logger.error(
                f"Partial fill: {success_count}/{len(order.legs)} legs placed. "
                "Attempting to close partial positions."
            )
            await self._close_partial_fills(order.group_id)
            return False

    async def _place_option_leg(self, leg: OptionLeg) -> bool:
        """Place a single options leg order via MCP."""
        args = {
            "symbol": leg.symbol.strip(),
            "qty": str(leg.qty),
            "side": leg.side,
            "type": "market",
            "time_in_force": "day",
        }
        result = await self._call("place_order", args)
        if self.dry_run:
            await self.state.add_log(fr"[dim][DRY-RUN] Placed {leg.side} x{leg.qty} {leg.symbol}[/]")
            return True  # Simulated success
            
        order_id = result.get("id") or result.get("order_id")
        if order_id:
            logger.info(f"Order placed: {leg.symbol} {leg.side} x{leg.qty}", extra={"order_id": order_id})
            await self.state.add_log(f"🟢 [bold green]FILLED:[/] {leg.side.upper()} {leg.qty}x {leg.symbol}")
            return True
            
        logger.error(f"Order placement returned no ID: {result}")
        await self.state.add_log(f"❌ [bold red]FAILED:[/] {leg.side.upper()} {leg.qty}x {leg.symbol}")
        return False

    async def close_position(self, symbol: str) -> bool:
        """Close an open position by OCC symbol."""
        logger.info(f"Closing position: {symbol}")
        result = await self._call("close_position", {"symbol": symbol})
        if self.dry_run or result.get("id") or result.get("order_id"):
            await self.state.remove_position(symbol)
            logger.info(f"Position closed: {symbol}")
            await self.state.add_log(f"🔴 [bold red]CLOSED:[/] Exited position on {symbol}")
            return True
        logger.error(f"Failed to close position {symbol}: {result}")
        return False

    async def _close_partial_fills(self, group_id: str):
        """Close all positions belonging to a group_id (cleanup after partial fill)."""
        to_close = [
            sym for sym, pos in self.state.positions.items()
            if pos.group_id == group_id
        ]
        for sym in to_close:
            await self.close_position(sym)
