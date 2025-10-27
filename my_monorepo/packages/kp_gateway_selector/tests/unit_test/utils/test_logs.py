import datetime
from decimal import Decimal
import json
import logging
import uuid
from unittest.mock import Mock, patch
import pytest

from kp_gateway_selector.utils.logs import (
    CustomFormatter,
    CustomJSONEncoder,
    JSONFormatter,
    setup_logger_json,
    CorrelationIdFilter
)


class TestCorrelationIdFilter:
    """Tests for CorrelationIdFilter."""

    def test_correlation_id_filter_works(self):
        """Test that CorrelationIdFilter works correctly."""
        filter_instance = CorrelationIdFilter()
        record = Mock()
        result = filter_instance.filter(record)
        # The filter should return True
        assert result is True


class TestCustomFormatter:
    """Tests for CustomFormatter."""

    def test_format_with_correlation_id(self):
        """Test formatting a log record with correlation_id."""
        formatter = CustomFormatter('%(name)s - %(levelname)s - %(correlation_id_str)s %(message)s')
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-correlation-id"

        result = formatter.format(record)

        assert "[test-correlation-id]" in result
        assert "Test message" in result

    def test_format_without_correlation_id(self):
        """Test formatting a log record without correlation_id."""
        formatter = CustomFormatter('%(name)s - %(levelname)s - %(correlation_id_str)s %(message)s')
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)

        assert "Test message" in result
        assert record.correlation_id_str == ""

    def test_format_with_extra_info(self):
        """Test formatting a log record with extra information."""
        formatter = CustomFormatter('%(message)s')
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.custom_field = "custom_value"
        record.user_id = 123

        result = formatter.format(record)

        assert "Test message" in result
        assert "custom_field=custom_value" in result
        assert "user_id=123" in result

    def test_format_without_extra_info(self):
        """Test formatting a log record without extra information."""
        formatter = CustomFormatter('%(message)s')
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)

        # The formatter may include some default fields like filename and taskName
        assert "Test message" in result


class TestCustomJSONEncoder:
    """Tests for CustomJSONEncoder."""

    def test_encode_uuid(self):
        """Test encoding UUID objects."""
        test_uuid = uuid.uuid4()
        encoder = CustomJSONEncoder()

        result = encoder.default(test_uuid)

        assert result == str(test_uuid)
        assert isinstance(result, str)

    def test_encode_decimal(self):
        """Test encoding Decimal objects."""
        test_decimal = Decimal("123.456")
        encoder = CustomJSONEncoder()

        result = encoder.default(test_decimal)

        assert result == 123.456
        assert isinstance(result, float)

    def test_encode_datetime(self):
        """Test encoding datetime objects."""
        test_datetime = datetime.datetime(2024, 1, 15, 10, 30, 45)
        encoder = CustomJSONEncoder()

        result = encoder.default(test_datetime)

        assert result == "2024-01-15T10:30:45"
        assert isinstance(result, str)

    def test_encode_unsupported_type(self):
        """Test encoding unsupported types raises TypeError."""
        encoder = CustomJSONEncoder()

        with pytest.raises(TypeError):
            encoder.default(object())


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_time(self):
        """Test formatTime method."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.formatTime(record)

        # Check that the result contains expected datetime format components
        assert len(result) > 0
        assert "-" in result  # Date separators
        assert ":" in result  # Time separators

    def test_format_basic_log(self):
        """Test formatting a basic log record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["logger"] == "test_logger"
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data
        assert log_data["exc_info"] is None

    def test_format_with_correlation_id(self):
        """Test formatting a log record with correlation_id."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-correlation-id"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["correlation_id"] == "test-correlation-id"

    def test_format_without_correlation_id(self):
        """Test formatting a log record without correlation_id."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert "correlation_id" not in log_data

    def test_format_with_exception(self):
        """Test formatting a log record with exception info."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["level"] == "ERROR"
        assert log_data["message"] == "Error occurred"
        assert log_data["exc_info"] is not None
        assert "ValueError" in log_data["exc_info"]
        assert "Test exception" in log_data["exc_info"]

    def test_format_with_extra_fields(self):
        """Test formatting a log record with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.extra = {"user_id": 123, "request_id": "abc"}

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["user_id"] == 123
        assert log_data["request_id"] == "abc"

    def test_format_with_custom_fields(self):
        """Test formatting a log record with custom fields in __dict__."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.custom_field = "custom_value"
        record.transaction_id = "txn-123"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["custom_field"] == "custom_value"
        assert log_data["transaction_id"] == "txn-123"


class TestSetupLoggerJson:
    """Tests for setup_logger_json function."""

    def test_setup_logger_debug_level(self):
        """Test setting up logger with DEBUG level."""
        logger = setup_logger_json(level="DEBUG", module_name="test_module")

        assert logger.name == "kp_gateway_selector.test_module"
        assert logger.level == logging.DEBUG
        assert logger.propagate is False
        assert len(logger.handlers) > 0

    def test_setup_logger_info_level(self):
        """Test setting up logger with INFO level."""
        logger = setup_logger_json(level="INFO", module_name="test_module_info")

        assert logger.name == "kp_gateway_selector.test_module_info"
        assert logger.level == logging.INFO

    def test_setup_logger_warning_level(self):
        """Test setting up logger with WARNING level."""
        logger = setup_logger_json(level="WARNING", module_name="test_module_warning")

        assert logger.name == "kp_gateway_selector.test_module_warning"
        assert logger.level == logging.WARNING

    def test_setup_logger_error_level(self):
        """Test setting up logger with ERROR level."""
        logger = setup_logger_json(level="ERROR", module_name="test_module_error")

        assert logger.name == "kp_gateway_selector.test_module_error"
        assert logger.level == logging.ERROR

    def test_setup_logger_critical_level(self):
        """Test setting up logger with CRITICAL level."""
        logger = setup_logger_json(level="CRITICAL", module_name="test_module_critical")

        assert logger.name == "kp_gateway_selector.test_module_critical"
        assert logger.level == logging.CRITICAL

    def test_setup_logger_clears_handlers(self):
        """Test that setup_logger_json clears existing handlers."""
        logger = setup_logger_json(level="INFO", module_name="test_clear_handlers")
        initial_handler_count = len(logger.handlers)

        # Setup again
        logger = setup_logger_json(level="INFO", module_name="test_clear_handlers")

        # Should still have the same number of handlers (old ones cleared)
        assert len(logger.handlers) == initial_handler_count

    def test_setup_logger_has_json_formatter(self):
        """Test that the logger uses JSONFormatter."""
        logger = setup_logger_json(level="INFO", module_name="test_json_formatter")

        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logger_has_correlation_id_filter(self):
        """Test that the logger has CorrelationIdFilter."""
        logger = setup_logger_json(level="INFO", module_name="test_correlation_filter")

        # Check that at least one filter is a CorrelationIdFilter
        has_correlation_filter = any(
            isinstance(f, CorrelationIdFilter) for f in logger.filters
        )
        assert has_correlation_filter
