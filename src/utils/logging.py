"""
Daily logging configuration with automatic cleanup.

Logs all terminal output to daily timestamped files with 30-day retention.
Manages both file and console output streams.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def setup_daily_logging(
    retention_days: int = 30, log_dir: Optional[str] = None
) -> None:
    """
    Configure logging to daily timestamped files.

    Sets up simultaneous logging to:
    - Daily log file (YYYY-MM-DD.log format)
    - Console (stdout)
    - Proper UTF-8 encoding for international characters

    Automatically deletes log files older than retention period.

    Args:
        retention_days: Number of days to retain log files. Default 30.
        log_dir: Directory for log files. Default is ./logs.
    """
    # Determine log directory
    if log_dir is None:
        script_dir = Path(__file__).parent.parent.parent
        log_dir = script_dir / "logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(parents=True, exist_ok=True)

    # Create log filename with today's date
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logging.info("=== Logging initialized ===")

    # Redirect stdout and stderr
    sys.stdout = StreamToLogger(logging.getLogger(), logging.INFO)
    sys.stderr = StreamToLogger(logging.getLogger(), logging.ERROR)

    # Cleanup old logs
    cleanup_old_logs(str(log_dir), retention_days)


def cleanup_old_logs(log_dir: str, retention_days: int) -> None:
    """
    Delete log files older than retention period.

    Args:
        log_dir: Directory containing log files.
        retention_days: Number of days to retain files.
    """
    try:
        log_path = Path(log_dir)
        now = datetime.now()
        cutoff_date = now - timedelta(days=retention_days)

        for log_file in log_path.glob("*.log"):
            try:
                # Parse date from filename (format: YYYY-MM-DD.log)
                date_str = log_file.stem  # Gets filename without extension
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff_date:
                    log_file.unlink()
                    logging.info(f"Deleted old log: {log_file.name}")

            except (ValueError, OSError) as e:
                # Skip files that don't match format or can't be deleted
                logging.debug(f"Could not process log file {log_file.name}: {e}")

    except Exception as e:
        logging.error(f"Error during log cleanup: {e}")


class StreamToLogger:
    """
    Redirect standard output/error streams to Python logger.

    Captures print statements and error messages, redirecting them to
    the logging system while maintaining compatibility with code that
    expects sys.stdout/stderr.
    """

    def __init__(self, logger: logging.Logger, level: int) -> None:
        """
        Initialize stream redirector.

        Args:
            logger: Logger instance to send output to.
            level: Logging level (INFO, ERROR, DEBUG, etc.).
        """
        self.logger = logger
        self.level = level
        self.line_buffer = ""

    def write(self, message: str) -> None:
        """
        Write message to logger.

        Args:
            message: Message to log.
        """
        if message.strip():
            try:
                self.logger.log(self.level, message.strip())
            except UnicodeEncodeError:
                # Handle encoding errors gracefully
                safe_message = message.encode("utf-8", errors="ignore").decode("utf-8")
                self.logger.log(self.level, safe_message)

    def flush(self) -> None:
        """Flush operation (required for Python stream compatibility)."""
        pass


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger instance.

    Args:
        name: Logger name (typically __name__ from module).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
