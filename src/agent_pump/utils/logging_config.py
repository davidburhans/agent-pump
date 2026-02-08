"""Structured logging configuration for Agent Pump."""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            }:
                log_data[key] = value

        return json.dumps(log_data, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter with level-based colors."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        log_msg = (
            f"{color}[{timestamp}] [{record.levelname}] {record.name}: {record.getMessage()}{reset}"
        )

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            if exc_text:
                log_msg += f"\n{exc_text}"

        return log_msg


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    structured: bool = False,
    console_level: str | None = None,
) -> None:
    """
    Configure application logging.

    Args:
        level: Default log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for structured JSON logs
        structured: Whether to use structured JSON logging
        console_level: Optional separate level for console output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_level = console_level or level
    console_handler.setLevel(getattr(logging, console_level.upper()))

    if structured:
        console_handler.setFormatter(StructuredLogFormatter())
    else:
        console_handler.setFormatter(ColoredConsoleFormatter())

    root_logger.addHandler(console_handler)

    # File handler for structured logs
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(StructuredLogFormatter())
        root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info(f"Logging configured: level={level}, structured={structured}")


def set_log_level(level: str) -> None:
    """Change log level at runtime."""
    logging.getLogger().setLevel(getattr(logging, level.upper()))
    logging.getLogger(__name__).info(f"Log level changed to {level}")
