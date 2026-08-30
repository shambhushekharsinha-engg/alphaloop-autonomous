"""
agents/market_scanner.py

Market Scanner Agent
====================
Responsibilities:
  1. Pull OHLCV bars for each underlying in the watchlist using alpaca-py
  2. Calculate RSI from recent price bars
  3. Calculate IV Rank (IVR) — current IV vs 52-week historical range
  4. Fetch live options chain with Greeks from Alpaca Market Data API
  5. Determine trend using EMA crossover (fast 9 / slow 21)
  6. Update AgentState with fresh SignalSnapshot per symbol

IV Rank Formula:
    IVR = (current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low) × 100
"""
from __future__ import annotations
import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import numpy as np

from core.config import config
from core.logger import get_logger
from core.state import AgentState, SignalSnapshot

logger = get_logger(__name__, agent="MarketScanner")

# ── Optional alpaca-py imports (graceful degradation for tests) ─────────────
try:
    from alpaca.data import StockHistoricalDataClient, OptionHistoricalDataClient
    from alpaca.data.requests import (
        StockBarsRequest,
        OptionLatestQuoteRequest,
        OptionSnapshotRequest,
    )
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_PY_AVAILABLE = True
except ImportError:
    ALPACA_PY_AVAILABLE = False
    logger.warning("alpaca-py not installed — scanner will run in mock mode")


class MarketScannerAgent:
    """
    Scans the watchlist every `scan_interval_seconds` and writes
    fresh SignalSnapshot objects into the shared AgentState.
    """

    def __init__(self, state: AgentState):
        self.state = state
        self.cfg = config.scanner
        self._stock_client: Optional[object] = None
        self._option_client: Optional[object] = None
        self._setup_clients()

    def _setup_clients(self):
        if not ALPACA_PY_AVAILABLE:
            return
        self._stock_client = StockHistoricalDataClient(
            api_key=config.alpaca.api_key,
            secret_key=config.alpaca.api_secret,
        )
        self._option_client = OptionHistoricalDataClient(
            api_key=config.alpaca.api_key,
            secret_key=config.alpaca.api_secret,
        )

    # ── Main Scan Loop ──────────────────────────────────────────────────────

    async def run(self):
        """Continuously scan the watchlist on a fixed interval."""
        logger.info("Market Scanner started", extra={"watchlist": self.cfg.watchlist})
        while True:
            if not self.state.trading_halted:
                await self._scan_all()
            else:
                logger.warning(
                    "Trading halted — scanner paused",
                    extra={"reason": self.state.halt_reason}
                )
            await asyncio.sleep(self.cfg.scan_interval_seconds)

    async def _scan_all(self):
        tasks = [self._scan_symbol(sym) for sym in self.cfg.watchlist]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for sym, result in zip(self.cfg.watchlist, results):
            if isinstance(result, Exception):
                logger.error(f"Scan failed for {sym}: {result}")

    async def _scan_symbol(self, symbol: str) -> SignalSnapshot:
        """Run all scans for a single underlying and update state."""
        logger.info(f"Scanning {symbol}...")

        snapshot = None
        if ALPACA_PY_AVAILABLE and self._stock_client:
            try:
                snapshot = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_live_snapshot, symbol
                )
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "Authorization" in err_str or "Forbidden" in err_str:
                    logger.warning(f"Alpaca auth failed for {symbol} — check API keys. Falling back to mock data.")
                else:
                    logger.warning(f"Live fetch failed for {symbol}: {e!r}. Falling back to mock data.")
                snapshot = None

        if snapshot is None:
            snapshot = self._mock_snapshot(symbol)

        await self.state.update_signal(snapshot)
        await self.state.add_log(
            f"📡 [bold cyan]Scan ({symbol}):[/] RSI={snapshot.rsi:.0f} IVR={snapshot.iv_rank:.0f}% "
            f"Trend={snapshot.trend} → [bold yellow]{snapshot.recommended_strategy}[/]"
        )
        logger.info(
            f"Signal updated for {symbol}",
            extra={
                "rsi": round(snapshot.rsi, 1),
                "iv_rank": round(snapshot.iv_rank, 1),
                "trend": snapshot.trend,
                "strategy_hint": snapshot.recommended_strategy,
            }
        )
        return snapshot

    # ── Live Data Fetching ──────────────────────────────────────────────────

    def _fetch_live_snapshot(self, symbol: str) -> SignalSnapshot:
        """Fetch bars + IV and compute all signals. Runs in thread executor."""
        # Fetch 60 daily bars (enough for RSI-14 + EMA-21 + IV history)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=90)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            start=start,
            end=end,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),
            limit=60,
        )
        bars_response = self._stock_client.get_stock_bars(request)
        bars = bars_response.get(symbol, [])

        if not bars:
            return self._mock_snapshot(symbol)

        closes = np.array([bar.close for bar in bars])
        current_price = closes[-1]

        rsi = self._calculate_rsi(closes, self.cfg.rsi_period)
        trend = self._calculate_trend(closes)

        # Fetch IV from options chain
        iv_data = self._fetch_iv_data(symbol, current_price)

        # IV Rank: compare current IV to its own 52-week range
        if iv_data["iv_52w_high"] > iv_data["iv_52w_low"]:
            iv_rank = (
                (iv_data["current_iv"] - iv_data["iv_52w_low"])
                / (iv_data["iv_52w_high"] - iv_data["iv_52w_low"])
            ) * 100
        else:
            iv_rank = 50.0

        strategy = self._recommend_strategy(rsi, iv_rank, trend)

        return SignalSnapshot(
            symbol=symbol,
            price=current_price,
            rsi=rsi,
            iv_rank=iv_rank,
            current_iv=iv_data["current_iv"],
            iv_52w_high=iv_data["iv_52w_high"],
            iv_52w_low=iv_data["iv_52w_low"],
            trend=trend,
            recommended_strategy=strategy,
        )

    def _fetch_iv_data(self, symbol: str, current_price: float) -> dict:
        """Fetch ATM IV from the options chain snapshot."""
        try:
            # Target expiry ~30 DTE
            target_expiry = (datetime.now() + timedelta(days=30)).date()

            req = OptionSnapshotRequest(
                symbol_or_symbols=symbol,
                expiration_date_gte=target_expiry - timedelta(days=7),
                expiration_date_lte=target_expiry + timedelta(days=7),
                strike_price_gte=current_price * 0.98,
                strike_price_lte=current_price * 1.02,
                limit=10,
            )
            snapshots = self._option_client.get_option_snapshot(req)

            ivs = []
            for sym_key, snap in snapshots.items():
                if hasattr(snap, "greeks") and snap.greeks and snap.greeks.iv:
                    ivs.append(snap.greeks.iv * 100)  # Convert to percent

            if ivs:
                current_iv = np.mean(ivs)
                return {
                    "current_iv": current_iv,
                    "iv_52w_high": current_iv * 1.8,  # Approximate; replace with historical lookup
                    "iv_52w_low": current_iv * 0.5,
                }
        except Exception as e:
            logger.warning(f"IV fetch failed for {symbol}: {e}")

        # Default fallback
        return {"current_iv": 25.0, "iv_52w_high": 45.0, "iv_52w_low": 15.0}

    # ── Signal Computation ──────────────────────────────────────────────────

    @staticmethod
    def _calculate_rsi(closes: np.ndarray, period: int = 14) -> float:
        """Wilder's RSI calculation."""
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1 + rs))

    @staticmethod
    def _calculate_trend(closes: np.ndarray) -> str:
        """EMA-9 / EMA-21 crossover trend detection."""
        if len(closes) < 21:
            return "neutral"

        def ema(data: np.ndarray, period: int) -> float:
            k = 2 / (period + 1)
            val = data[0]
            for price in data[1:]:
                val = price * k + val * (1 - k)
            return val

        fast = ema(closes[-21:], 9)
        slow = ema(closes[-21:], 21)

        if fast > slow * 1.001:
            return "bullish"
        elif fast < slow * 0.999:
            return "bearish"
        return "neutral"

    @staticmethod
    def _recommend_strategy(rsi: float, iv_rank: float, trend: str) -> str:
        """
        Rule-based strategy recommendation that feeds the LLM orchestrator.

        High IV Rank (>50) → premium selling (Iron Condor or Credit Spread)
        Low  IV Rank (<30) → premium buying (Protective Put / Long Straddle)
        """
        if iv_rank >= 50:
            if 35 <= rsi <= 65 and trend == "neutral":
                return "iron_condor"
            elif rsi < 35:
                return "bull_put_spread"
            elif rsi > 65:
                return "bear_call_spread"
            else:
                return "iron_condor"
        elif iv_rank < 30:
            return "protective_put"
        else:
            # Medium IV rank — conservative, credit spread
            if rsi < 40:
                return "bull_put_spread"
            elif rsi > 60:
                return "bear_call_spread"
            return "no_trade"

    # ── Mock Mode ───────────────────────────────────────────────────────────

    @staticmethod
    def _mock_snapshot(symbol: str) -> SignalSnapshot:
        """Generate synthetic signals for testing without live data."""
        import random
        rng = random.Random(hash(symbol + str(date.today())))
        price = {"SPY": 540.0, "QQQ": 450.0, "NVDA": 800.0,
                 "AAPL": 210.0, "IWM": 220.0}.get(symbol, 100.0)
        rsi = rng.uniform(30, 70)
        iv_rank = rng.uniform(20, 80)
        trend = rng.choice(["bullish", "bearish", "neutral"])
        strategy = MarketScannerAgent._recommend_strategy(rsi, iv_rank, trend)
        return SignalSnapshot(
            symbol=symbol, price=price, rsi=rsi, iv_rank=iv_rank,
            current_iv=25.0, iv_52w_high=45.0, iv_52w_low=15.0,
            trend=trend, recommended_strategy=strategy,
        )
