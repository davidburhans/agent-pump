"""Unit tests for logging configuration."""

import json
import logging
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.utils.logging_config import (
    ColoredConsoleFormatter,
    StructuredLogFormatter,
    configure_logging,
    set_log_level,
)


class TestStructuredLogFormatter:
    """Tests for StructuredLogFormatter."""

    @pytest.fixture
    def formatter(self) -> StructuredLogFormatter:
        """Create a formatter instance."""
        return StructuredLogFormatter()

    @pytest.fixture
    def log_record(self) -> logging.LogRecord:
        """Create a basic log record."""
        return logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

    def test_basic_format(
        self, formatter: StructuredLogFormatter, log_record: logging.LogRecord
    ) -> None:
        """Test basic JSON formatting."""
        output = formatter.format(log_record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Test message"
        assert parsed["module"] == "test"
        assert parsed["function"] is None
        assert parsed["line"] == 42
        assert "timestamp" in parsed

    def test_timestamp_format(
        self, formatter: StructuredLogFormatter, log_record: logging.LogRecord
    ) -> None:
        """Test that timestamp is ISO format."""
        output = formatter.format(log_record)
        parsed = json.loads(output)

        # Should be valid ISO format
        assert "T" in parsed["timestamp"]
        assert (
            parsed["timestamp"].endswith("Z")
            or "+" in parsed["timestamp"]
            or "-" in parsed["timestamp"][-6:]
        )

    def test_exception_formatting(self, formatter: StructuredLogFormatter) -> None:
        """Test exception formatting in JSON."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "Test exception" in parsed["exception"]

    def test_extra_fields(self, formatter: StructuredLogFormatter) -> None:
        """Test that extra fields are included."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.another_field = 123

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["custom_field"] == "custom_value"
        assert parsed["another_field"] == 123

    def test_different_log_levels(self, formatter: StructuredLogFormatter) -> None:
        """Test formatting with different log levels."""
        for level, level_name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg=f"{level_name} message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            parsed = json.loads(output)

            assert parsed["level"] == level_name


class TestColoredConsoleFormatter:
    """Tests for ColoredConsoleFormatter."""

    @pytest.fixture
    def formatter(self) -> ColoredConsoleFormatter:
        """Create a formatter instance."""
        return ColoredConsoleFormatter()

    @pytest.fixture
    def log_record(self) -> logging.LogRecord:
        """Create a basic log record."""
        return logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

    def test_basic_format(
        self, formatter: ColoredConsoleFormatter, log_record: logging.LogRecord
    ) -> None:
        """Test basic colored formatting."""
        output = formatter.format(log_record)

        assert "INFO" in output
        assert "test_logger" in output
        assert "Test message" in output
        assert "[" in output  # Should have timestamp brackets

    def test_colors_by_level(self, formatter: ColoredConsoleFormatter) -> None:
        """Test that different levels have different colors."""
        colors = {}

        for level, level_name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg=f"{level_name} message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            color_code = output[:5]  # Get ANSI escape code
            colors[level_name] = color_code

        # All levels should have different colors (or at least not all the same)
        assert len(set(colors.values())) > 1


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_basic_configuration(self) -> None:
        """Test basic logging configuration."""
        # Reset root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)

        configure_logging(level="INFO", structured=False)

        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) == 1  # Console handler only
        assert isinstance(root_logger.handlers[0], logging.StreamHandler)

    def test_debug_level(self) -> None:
        """Test setting DEBUG level."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        configure_logging(level="DEBUG", structured=False)

        assert root_logger.level == logging.DEBUG

    def test_structured_logging(self) -> None:
        """Test structured JSON logging."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        configure_logging(level="INFO", structured=True)

        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, StructuredLogFormatter)

    def test_file_logging(self, tmp_path: Path) -> None:
        """Test file logging configuration."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        log_file = tmp_path / "test.log"
        configure_logging(level="INFO", structured=True, log_file=log_file)

        assert len(root_logger.handlers) == 2  # Console + file
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1
        assert file_handlers[0].baseFilename == str(log_file)

    def test_file_logging_creates_directories(self, tmp_path: Path) -> None:
        """Test that file logging creates parent directories."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        log_file = tmp_path / "nested" / "dir" / "test.log"
        configure_logging(level="INFO", log_file=log_file)

        assert log_file.parent.exists()

    def test_console_level_override(self) -> None:
        """Test different level for console vs default."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        configure_logging(level="DEBUG", structured=False, console_level="ERROR")

        # Root logger should be DEBUG
        assert root_logger.level == logging.DEBUG

        # But console handler should be ERROR
        console_handler = root_logger.handlers[0]
        assert console_handler.level == logging.ERROR

    def test_handler_cleanup(self) -> None:
        """Test that old handlers are removed."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Add some dummy handlers
        root_logger.addHandler(logging.NullHandler())
        root_logger.addHandler(logging.StreamHandler())

        assert len(root_logger.handlers) == 2

        configure_logging(level="INFO")

        # Should have replaced them
        assert len(root_logger.handlers) == 1


class TestSetLogLevel:
    """Tests for set_log_level function."""

    def test_set_log_level_runtime(self) -> None:
        """Test changing log level at runtime."""
        # Configure initial state
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        configure_logging(level="INFO")

        assert root_logger.level == logging.INFO

        # Change level
        set_log_level("DEBUG")

        assert root_logger.level == logging.DEBUG

    def test_set_different_levels(self) -> None:
        """Test setting various log levels."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        configure_logging(level="DEBUG")

        levels_to_test = ["WARNING", "ERROR", "CRITICAL"]

        for level in levels_to_test:
            set_log_level(level)
            expected = getattr(logging, level)
            assert root_logger.level == expected


class TestIntegrationLogging:
    """Integration tests for logging."""

    def test_actual_log_output(self, capsys: pytest.CaptureFixture) -> None:
        """Test actual log output."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        configure_logging(level="INFO", structured=False)

        # Log a message
        test_logger = logging.getLogger("test_integration")
        test_logger.info("Integration test message")

        # Check output
        captured = capsys.readouterr()
        assert (
            "Integration test message" in captured.err or "Integration test message" in captured.out
        )

    def test_json_log_output(self, tmp_path: Path) -> None:
        """Test JSON log output to file."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        log_file = tmp_path / "structured.log"
        configure_logging(level="INFO", structured=True, log_file=log_file)

        # Log a message
        test_logger = logging.getLogger("test_json")
        test_logger.info("JSON test message")

        # Force flush
        for handler in root_logger.handlers:
            handler.flush()

        # Read and verify
        log_content = log_file.read_text()
        lines = log_content.strip().split("\n")
        last_line = lines[-1]

        parsed = json.loads(last_line)
        assert parsed["message"] == "JSON test message"
        assert parsed["logger"] == "test_json"
        assert parsed["level"] == "INFO"
