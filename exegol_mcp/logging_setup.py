"""Logging configuration for Exegol MCP."""

import json
import logging
import sys
from datetime import datetime, timezone

from .models import Config


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "container_name"):
            log_data["container_name"] = record.container_name
        if hasattr(record, "command"):
            log_data["command"] = record.command
        if hasattr(record, "exit_code"):
            log_data["exit_code"] = record.exit_code
        if hasattr(record, "execution_time_ms"):
            log_data["execution_time_ms"] = record.execution_time_ms

        return json.dumps(log_data)


def setup_logging(config: Config) -> logging.Logger:
    """Setup structured logging based on configuration.

    Args:
        config: Server configuration

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("exegol_mcp")
    logger.setLevel(getattr(logging, config.log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stderr)

    # Set formatter based on config
    if config.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    logger.addHandler(handler)
    return logger
