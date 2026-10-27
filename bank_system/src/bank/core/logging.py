"""Uniform JSON/text logging with a shared service context.

Every service attaches its ``service_name`` to each record so a single
docker-compose log stream remains attributable.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class ServiceContextFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "service": getattr(record, "service", ""),
            "level": record.levelname,
            "ts": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(service: str, level: str = "INFO", json_mode: bool = False) -> None:
    """Configure the root logger once (idempotent across uvicorn reloads)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JSONFormatter(separators=(",", ":"))
        if json_mode
        else logging.Formatter("[%(levelname)s] %(service)s %(name)s: %(message)s")
    )
    handler.addFilter(ServiceContextFilter(service))
    root.addHandler(handler)
    root.setLevel(level.strip().upper())

    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers.clear()
    uvicorn_error.addHandler(handler)
    uvicorn_error.propagate = False


def get_logger(name: str, service: str = "bank-system") -> logging.LoggerAdapter:
    """Return an adapter that stamps ``service`` onto every record."""
    return logging.LoggerAdapter(logging.getLogger(name), {"service": service})