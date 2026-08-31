"""
core/config.py
Centralized configuration management for AlphaLoop Autonomous.
Reads all settings from environment variables with sane defaults.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AlpacaConfig:
    api_key: str = field(default_factory=lambda: os.environ.get("APCA_API_KEY_ID", ""))
    api_secret: str = field(default_factory=lambda: os.environ.get("APCA_API_SECRET_KEY", ""))
    paper: bool = field(default_factory=lambda: os.environ.get("ALPACA_PAPER", "true").lower() == "true")

    @property
    def base_url(self) -> str:
        return "https://paper-api.alpaca.markets" if self.paper else "https://api.alpaca.markets"

    def validate(self):
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Missing Alpaca API credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in .env"
            )


@dataclass
class GeminiConfig:
    api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    enabled: bool = field(default_factory=lambda: bool(os.environ.get("GEMINI_API_KEY", "")))


@dataclass
class RiskConfig:
    # Maximum fraction of equity per single trade (5%)
    max_position_pct: float = float(os.environ.get("MAX_POSITION_PCT", "0.05"))
    # Maximum total portfolio delta allowed (market-neutral bias)
    max_portfolio_delta: float = float(os.environ.get("MAX_PORTFOLIO_DELTA", "0.20"))
    # Intraday loss limit — halt if daily P&L drops below this fraction of equity
    daily_loss_limit_pct: float = float(os.environ.get("DAILY_LOSS_LIMIT_PCT", "0.03"))
    # Maximum concurrent open options positions
    max_concurrent_positions: int = int(os.environ.get("MAX_CONCURRENT_POSITIONS", "5"))
    # Stop-loss on individual position: close if loss > this fraction of premium received
    position_stop_loss_pct: float = float(os.environ.get("POSITION_STOP_LOSS_PCT", "0.30"))
    # Required account starting balance (hackathon rule)
    required_starting_balance: float = float(os.environ.get("REQUIRED_STARTING_BALANCE", "100000.0"))


@dataclass
class ScannerConfig:
    # Underlyings to scan
    watchlist: list = field(default_factory=lambda: [
        sym.strip() for sym in
        os.environ.get("WATCHLIST", "SPY,QQQ,NVDA,AAPL,IWM").split(",")
    ])
    # Target DTE range for option selection (days to expiry)
    min_dte: int = int(os.environ.get("MIN_DTE", "7"))
    max_dte: int = int(os.environ.get("MAX_DTE", "45"))
    # IV Rank thresholds
    high_ivr_threshold: float = float(os.environ.get("HIGH_IVR_THRESHOLD", "50.0"))
    low_ivr_threshold: float = float(os.environ.get("LOW_IVR_THRESHOLD", "30.0"))
    # RSI period
    rsi_period: int = int(os.environ.get("RSI_PERIOD", "14"))
    # Scan interval in seconds
    scan_interval_seconds: int = int(os.environ.get("SCAN_INTERVAL_SECONDS", "300"))


@dataclass
class AppConfig:
    alpaca: AlpacaConfig = field(default_factory=AlpacaConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    dry_run: bool = field(default_factory=lambda: os.environ.get("DRY_RUN", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    def validate(self):
        self.alpaca.validate()


# Singleton config instance
config = AppConfig()
