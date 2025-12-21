"""Logging configuration for Book Creator.

Provides a single entry point to configure logging consistently across the app.

Requirements:
- Log to stdout for interactive debugging.
- Log to a rotating file inside the current project folder (working folder).

The app calls :func:`configure_logging` on startup, and can call it again when the
working folder changes.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


DEFAULT_LOG_FILENAME = "book_creator.log"


def configure_logging(
    *,
    project_folder: Optional[Path],
    level: int = logging.INFO,
) -> Path:
    """Configure root logging handlers.

    Args:
        project_folder: Folder where logs should be written. When None, uses the
            current working directory.
        level: Root log level.

    Returns:
        The resolved path to the log file.
    """
    resolved_project = (project_folder or Path.cwd()).resolve()
    log_dir = resolved_project / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / DEFAULT_LOG_FILENAME

    root = logging.getLogger()
    root.setLevel(level)

    # Replace handlers to avoid duplicate logs if configure_logging is called
    # multiple times (e.g., when the working folder changes).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root.addHandler(stream_handler)
    root.addHandler(file_handler)

    # Keep noisy libraries from drowning our logs.
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return log_file
