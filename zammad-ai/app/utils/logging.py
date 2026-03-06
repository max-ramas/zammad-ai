import json
import logging
import logging.config
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from yaml import safe_load


@lru_cache(maxsize=1)
def get_log_config() -> dict[str, Any]:
    """Generate logging configuration dict based on settings.

    This function is cached to ensure the configuration is only generated once per process.

    Returns:
        dict[str, Any]: Logging configuration dictionary.
    """
    from app.settings import get_settings

    settings = get_settings()

    # Read logconf.yaml as template
    with open("logconf.yaml", "r", encoding="utf-8") as file:
        log_config = safe_load(file)

    # Determine formatter based on settings
    # "plain" format uses the "simple" formatter from logconf.yaml
    formatter = "simple" if (settings.log.format == "plain" or settings.mode == "development") else "json"

    # Update all handlers to use the configured formatter
    for handler_config in log_config.get("handlers", {}).values():
        if "formatter" in handler_config:
            handler_config["formatter"] = formatter

    # Set log level for zammad-ai logger
    if "loggers" in log_config and "zammad-ai" in log_config["loggers"]:
        log_config["loggers"]["zammad-ai"]["level"] = settings.log.level

    return log_config


def getLogger(name: str = "zammad-ai") -> logging.Logger:
    """Configures logging and returns a logger with the specified name.

    Logging configuration is only performed once per process via cached log config.
    Subsequent calls return loggers without reconfiguring.

    Parameters:
        name (str): The name of the logger.

    Returns:
        logging.Logger: The logger with the specified name.
    """
    log_config = get_log_config()
    logging.config.dictConfig(log_config)
    return logging.getLogger(name)


class JsonFormatter(logging.Formatter):
    """A custom JSON formatter for logging."""

    # Standard LogRecord attributes to exclude
    STANDARD_ATTRIBUTES: set[str] = {
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
        "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record as a JSON string.

        Parameters:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The log record as a JSON string.
        """
        #
        log_data = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields that were passed via the extra parameter

        # Add any attributes that aren't standard LogRecord attributes
        for key, value in record.__dict__.items():
            if key not in self.STANDARD_ATTRIBUTES and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)
