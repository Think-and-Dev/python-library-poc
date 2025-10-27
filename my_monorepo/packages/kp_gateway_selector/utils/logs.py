import datetime
from decimal import Decimal
import json
import logging
from typing import Any, Optional
import uuid

from asgi_correlation_id import CorrelationIdFilter
from kp_gateway_selector.postgresql.database import LOG_SOURCE


class CustomFormatter(logging.Formatter):
    def format(self, record):
        record.correlation_id_str = f"[{record.correlation_id}]" if hasattr(record, "correlation_id") and record.correlation_id is not None else ""
        msg = super().format(record)
        extra_info = " ".join(f"{k}={v}" for k, v in record.__dict__.items() if k not in ["msg", "name","args",
                                                                                          "module", "message", "asctime",
                                                                                          "lineno", "thread", "threadName",
                                                                                          "levelno", "levelname", "funcName",
                                                                                          "pathname", "exc_info", "exc_text",
                                                                                          "stack_info", "threadName", "processName",
                                                                                          "process", "processName", "relativeCreated",
                                                                                          "created", "msecs","correlation_id_str",
                                                                                          "correlation_id"
                                                                                          ])
        if extra_info:
            msg = f"{msg} ({extra_info})"
        return msg

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUID, Decimal, and datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


class JSONFormatter(logging.Formatter):
    """A formatter that outputs logs in JSON format for CloudWatch."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Override formatTime to include timezone information and microseconds."""
        # Simply use datetime directly with its own formatting
        dt = datetime.datetime.fromtimestamp(record.created).astimezone()
        # Format: YYYY-MM-DD HH:MM:SS.microseconds+TZOFFSET
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f%z")

    def format(self, record: logging.LogRecord) -> str:
        # Get the original message
        log_data: dict[str, Optional[str]] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if hasattr(record, "correlation_id") and record.correlation_id is not None:
            log_data["correlation_id"] = record.correlation_id

        # Add exception info if available
        if record.exc_info:
            import traceback

            exc_type, exc_value, exc_traceback = record.exc_info
            exc_info_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            log_data["exc_info"] = exc_info_str
        else:
            log_data["exc_info"] = None

        # Add extra fields from the record
        if hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)

        extra_info = {k: v for k, v in record.__dict__.items() if k not in ["msg", "name", "args", "module", "message",
                                                                            "asctime", "lineno", "thread", "threadName",
                                                                            "levelno", "levelname", "funcName", "pathname",
                                                                            "exc_info", "exc_text","stack_info", "threadName",
                                                                            "processName", "process", "processName",
                                                                            "relativeCreated", "created", "msecs","extra",
                                                                            "correlation_id"
                                                                            ]}
        if extra_info:
            log_data.update(extra_info)
        # Return as JSON string
        return json.dumps(log_data, cls=CustomJSONEncoder)

logger = logging.getLogger(LOG_SOURCE)
logger.setLevel(logging.INFO)
logger.addFilter(CorrelationIdFilter())
handler = logging.StreamHandler()
# Los logs que no estén relacionados con una request no tienen correlation_id
formatter = CustomFormatter('%(name)s - %(levelname)s - %(correlation_id_str)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def setup_logger_json(
    level: str,
    module_name: str,
) -> logging.Logger:
    """Configure and return a logger instance for the specified module.

    Args:
        module_name: Name of the module requesting the logger
        level: Logging level (default: INFO)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(f"{LOG_SOURCE}.{module_name}")
    logger.handlers.clear()
    set_level = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    logger.setLevel(set_level[level])
    # Prevent propagation to avoid duplicate logs with Celery's logger
    logger.propagate = False

    # Add correlation id filter
    logger.addFilter(CorrelationIdFilter())

    # Console handler for CloudWatch with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    json_formatter = JSONFormatter()
    console_handler.setFormatter(json_formatter)
    logger.addHandler(console_handler)

    return logger
