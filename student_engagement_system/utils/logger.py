"""
Centralized logging configuration for the Student Engagement Monitoring System.

Usage
-----
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
"""
import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _loguru_logger

_CONFIGURED = False


def _project_root() -> Path:
    """Locate the project root (the directory containing this utils/ package)."""
    return Path(__file__).resolve().parent.parent


def configure_logging(config: Optional[dict] = None) -> None:
    """Configure loguru sinks exactly once per process.

    Args:
        config: Parsed contents of configs/logging.yaml. If ``None``, sensible
            defaults matching that file are used.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if config is None:
        config = {
            "level": "INFO",
            "rotation": "10 MB",
            "retention": "14 days",
            "compression": "zip",
            "log_files": {
                "application": "logs/application.log",
                "errors": "logs/errors.log",
                "training": "logs/training.log",
                "predictions": "logs/predictions.log",
            },
        }

    root = _project_root()
    _loguru_logger.remove()  # drop the default stderr sink; we define our own below

    # Human-readable console sink (development convenience).
    _loguru_logger.add(
        sys.stderr,
        level=config["level"],
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    log_files = config["log_files"]

    # General application log -- everything at configured level and above.
    _loguru_logger.add(
        root / log_files["application"],
        level=config["level"],
        rotation=config["rotation"],
        retention=config["retention"],
        compression=config["compression"],
        enqueue=True,
        filter=lambda record: record["extra"].get("stream", "application") == "application",
    )

    # Errors-only log -- ERROR and above, from any stream.
    _loguru_logger.add(
        root / log_files["errors"],
        level="ERROR",
        rotation=config["rotation"],
        retention=config["retention"],
        compression=config["compression"],
        enqueue=True,
    )

    # Training log -- only records explicitly tagged stream="training".
    _loguru_logger.add(
        root / log_files["training"],
        level="DEBUG",
        rotation=config["rotation"],
        retention=config["retention"],
        compression=config["compression"],
        enqueue=True,
        filter=lambda record: record["extra"].get("stream") == "training",
    )

    # Predictions log -- only records explicitly tagged stream="predictions".
    _loguru_logger.add(
        root / log_files["predictions"],
        level="DEBUG",
        rotation=config["rotation"],
        retention=config["retention"],
        compression=config["compression"],
        enqueue=True,
        filter=lambda record: record["extra"].get("stream") == "predictions",
    )

    _CONFIGURED = True


def get_logger(name: str = "app", stream: str = "application"):
    """Return a loguru logger bound to a module name and log stream.

    Args:
        name: Usually ``__name__`` of the calling module.
        stream: One of "application" (default), "training", or "predictions".
            Controls which dedicated log file the record is routed to, in
            addition to application.log/errors.log which always receive
            matching records.

    Returns:
        A loguru logger instance pre-bound with contextual metadata.
    """
    configure_logging()
    return _loguru_logger.bind(name=name, stream=stream)
