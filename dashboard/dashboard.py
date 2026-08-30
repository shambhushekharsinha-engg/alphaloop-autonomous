"""
dashboard/dashboard.py

Live Terminal Dashboard using Rich.
Displays Account State, Open Positions, and Recent Activity.
"""
import asyncio
import os
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from core.state import AgentState

class AlphaDashboard:
    def __init__(self, state: AgentState):
        self.state = state

    def _generate_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=2),
            Layout(name="logs", size=10)
        )
        layout["main"].split_row(
            Layout(name="positions", ratio=2),
            Layout(name="signals", ratio=1)
        )
        return layout

    def _build_header(self) -> Panel:
        status = "[red]HALTED[/]" if self.state.trading_halted else "[green]ACTIVE[/]"
        delta_color = "red" if self.state.portfolio_delta < 0 else "green"
        text = Text.from_markup(
            f" AlphaLoop Autonomous | Equity: ${self.state.equity:,.2f} | "
            f"Daily P&L: ${self.state.daily_pnl:,.2f} | "
            f"Net Delta: [{delta_color}]{self.state.portfolio_delta:.2f}[/] | "
            f"Status: {status}"
        )
        return Panel(text, style="bold blue")

    def _build_positions_table(self) -> Panel:
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Symbol")
        table.add_column("Strategy")
        table.add_column("Side")
        table.add_column("Qty", justify="right")
        table.add_column("Unrealized P&L", justify="right")

        for sym, pos in self.state.positions.items():
            pnl_color = "green" if pos.unrealized_pnl >= 0 else "red"
            table.add_row(
                sym,
                pos.strategy,
                pos.side,
                str(pos.qty),
                f"[{pnl_color}]${pos.unrealized_pnl:,.2f}[/]"
            )

        return Panel(table, title="Open Positions")

    def _build_signals_table(self) -> Panel:
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Ticker")
        table.add_column("RSI")
        table.add_column("IV Rank")
        table.add_column("Rec Strategy")

        for sym, sig in self.state.signals.items():
            table.add_row(
                sym,
                f"{sig.rsi:.1f}",
                f"{sig.iv_rank:.1f}%",
                sig.recommended_strategy
            )

        return Panel(table, title="Market Signals (Cache)")

    def _build_logs_panel(self) -> Panel:
        if not self.state.recent_logs:
            text = Text("Waiting for AI analysis...", style="dim italic")
        else:
            text = Text.from_markup("\n".join(self.state.recent_logs))
        return Panel(text, title="🧠 Live AI Agent Activity", border_style="green")

    async def run(self):
        """Run the live dashboard update loop."""
        # Only clear screen if not in dry-run/debug
        if os.environ.get("LOG_LEVEL") == "DEBUG":
            return

        with Live(refresh_per_second=2, screen=True) as live:
            while True:
                layout = self._generate_layout()
                layout["header"].update(self._build_header())
                layout["positions"].update(self._build_positions_table())
                layout["signals"].update(self._build_signals_table())
                layout["logs"].update(self._build_logs_panel())
                live.update(layout)
                await asyncio.sleep(0.5)
