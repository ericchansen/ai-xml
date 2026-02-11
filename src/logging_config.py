"""Logging configuration for the AI Workflow Authoring app."""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file with timestamp
LOG_FILE = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up logging with both file and console handlers."""

    # Create logger
    logger = logging.getLogger("ai_workflow")
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Format with timestamp, level, and message
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler - append mode, UTF-8 encoding
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler for errors only (less noise in Streamlit)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "ai_workflow") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def get_recent_logs(lines: int = 50) -> str:
    """Read recent log entries for display in UI."""
    if not LOG_FILE.exists():
        return "No logs yet."

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(recent)
    except Exception as e:
        return f"Error reading logs: {e}"


# Initialize logging on import
logger = setup_logging()
