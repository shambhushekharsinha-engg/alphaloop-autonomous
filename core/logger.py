"""
core/logger.py
Structured JSON logging for all agents and the dashboard.
"""
import logging
import sys
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for easy parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "agent": getattr(record, "agent", "system"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra_keys = {"agent", "msg", "ts", "level"}
        for key, val in record.__dict__.items():
            if not key.startswith("_") and key not in extra_keys and key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            }:
                payload[key] = val
        return json.dumps(payload)


def get_logger(name: str, agent: str = "system") -> logging.Logger:
    """Return a logger that emits structured JSON. All agents should call this."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    class AgentAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            kwargs.setdefault("extra", {})["agent"] = agent
            return msg, kwargs

    return AgentAdapter(logger, {})
