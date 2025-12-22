"""Tests for AI configuration loading.

Ensures ai_config.json exists and contains all required keys.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.services.ai_config import load_ai_config, AIConfigError


REQUIRED_MODELS = ["image_generation"]
REQUIRED_SYSTEM_PROMPTS = ["character_sheet", "page", "rework_character", "rework_page"]
REQUIRED_TEMPLATES = ["style_prefix", "rework_instruction"]


@pytest.mark.unit
def test_ai_config_json_exists_and_is_valid() -> None:
    """Verify ai_config.json exists at repository root and contains required keys."""
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "ai_config.json"
    assert config_path.exists(), "Expected ai_config.json at repository root"

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)

    # Check required models
    models = data.get("models", {})
    for model_key in REQUIRED_MODELS:
        assert model_key in models, f"Missing required model: {model_key}"
        assert isinstance(models[model_key], str) and models[model_key].strip()

    # Check required system prompts
    prompts = data.get("system_prompts", {})
    for prompt_key in REQUIRED_SYSTEM_PROMPTS:
        assert prompt_key in prompts, f"Missing required system prompt: {prompt_key}"
        assert isinstance(prompts[prompt_key], str) and prompts[prompt_key].strip()

    # Check required templates
    templates = data.get("templates", {})
    for template_key in REQUIRED_TEMPLATES:
        assert template_key in templates, f"Missing required template: {template_key}"
        assert (
            isinstance(templates[template_key], str) and templates[template_key].strip()
        )

    # Check supported_models_for_usage_tracking exists
    tracking = data.get("supported_models_for_usage_tracking", [])
    assert isinstance(tracking, list) and len(tracking) > 0


@pytest.mark.unit
def test_load_ai_config_raises_on_missing_file() -> None:
    """Verify AIConfigError is raised when config file is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        missing_path = Path(tmpdir) / "nonexistent.json"
        with pytest.raises(AIConfigError, match="not found"):
            load_ai_config(missing_path)


@pytest.mark.unit
def test_load_ai_config_raises_on_invalid_json() -> None:
    """Verify AIConfigError is raised when config file contains invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_json = Path(tmpdir) / "bad.json"
        bad_json.write_text("{ not valid json }", encoding="utf-8")
        with pytest.raises(AIConfigError, match="Invalid JSON"):
            load_ai_config(bad_json)
