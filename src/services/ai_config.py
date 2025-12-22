"""AI configuration loader.

Centralizes Gemini model names and system prompts in a single JSON file.

Default location: repository root `ai_config.json`.
Override location: set env var `BOOK_CREATOR_AI_CONFIG` to a JSON file path.

The goal is to let prompts/models be edited without changing code.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AIConfigError(Exception):
    """Raised when AI configuration cannot be loaded."""

    pass


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle; sys._MEIPASS is the temp folder/internal dir
        return Path(sys._MEIPASS)

    # src/services/ai_config.py -> src/services -> src -> repo root
    return Path(__file__).resolve().parents[2]


def get_ai_config_path(explicit_path: Optional[Path] = None) -> Path:
    """Resolve the AI config JSON path."""
    if explicit_path is not None:
        return explicit_path

    override = os.environ.get("BOOK_CREATOR_AI_CONFIG")
    if override:
        return Path(override)

    # Prefer repo root for local development and tests.
    return _repo_root() / "ai_config.json"


def load_ai_config(path: Optional[Path] = None) -> dict[str, Any]:
    """Load AI config from JSON.

    Raises:
        AIConfigError: If the file does not exist or is invalid JSON.
    """
    resolved = get_ai_config_path(path)

    if not resolved.exists():
        raise AIConfigError(f"AI config file not found: {resolved}")

    try:
        with open(resolved, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise AIConfigError(f"AI config must be a JSON object: {resolved}")
        return data
    except json.JSONDecodeError as exc:
        raise AIConfigError(
            f"Invalid JSON in AI config file {resolved}: {exc}"
        ) from exc


def get_model(name: str, *, config: Optional[dict[str, Any]] = None) -> str:
    cfg = config or load_ai_config()
    models = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    value = models.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise AIConfigError(f"Model '{name}' not found in ai_config.json")


def get_system_prompts(*, config: Optional[dict[str, Any]] = None) -> dict[str, str]:
    cfg = config or load_ai_config()
    prompts = (
        cfg.get("system_prompts") if isinstance(cfg.get("system_prompts"), dict) else {}
    )
    result: dict[str, str] = {}
    for key, value in prompts.items():
        if isinstance(value, str):
            result[str(key)] = value
    return result


def get_templates(*, config: Optional[dict[str, Any]] = None) -> dict[str, str]:
    cfg = config or load_ai_config()
    templates = cfg.get("templates") if isinstance(cfg.get("templates"), dict) else {}
    result: dict[str, str] = {}
    for key, value in templates.items():
        if isinstance(value, str):
            result[str(key)] = value
    return result


def get_supported_models_for_usage_tracking(
    *, config: Optional[dict[str, Any]] = None
) -> set[str]:
    cfg = config or load_ai_config()
    raw = cfg.get("supported_models_for_usage_tracking")
    models: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                models.add(item.strip())
    if models:
        return models

    # Fall back to configured model if no explicit list.
    models.add(get_model("image_generation", config=cfg))
    return models
