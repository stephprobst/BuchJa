"""Settings service for Book Creator.

Handles API key storage (via Windows Credential Locker) and
application configuration (JSON file).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

import keyring

from src.services.ai_config import get_supported_models_for_usage_tracking

logger = logging.getLogger(__name__)

# Constants
APP_NAME = "book_creator"
API_KEY_SERVICE = "gemini_api_key"
DEFAULT_ASPECT_RATIO = "3:4"
ASPECT_RATIOS = ["1:1", "3:4", "4:3", "16:9", "9:16"]

# Gemini usage tracking (persisted in config.json)
GEMINI_USAGE_KEY = "gemini_usage"

# Supported models for usage tracking (and enforced by the app).
# This is configured in ai_config.json, with these values as a safe fallback.
try:
    SUPPORTED_GEMINI_MODELS = get_supported_models_for_usage_tracking()
except Exception:  # pragma: no cover
    SUPPORTED_GEMINI_MODELS = {
        "gemini-3-pro-image-preview",
        "gemini-3-pro-preview",
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Settings:
    """Manages application settings and secure credential storage."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize settings manager.

        Args:
            config_path: Path to JSON config file. If None, uses default location.
        """
        self._config_path = config_path or self._get_default_config_path()
        self._config: dict = {}
        self._project_config: dict = {}

        # Batch update flags
        self._batch_mode = False
        self._pending_save_project = False
        self._pending_save_global = False

        self._load_config()
        if self.working_folder:
            self._load_project_config()

    @contextmanager
    def batch_updates(self):
        """Context manager to batch multiple settings updates into a single save operation."""
        self._batch_mode = True
        try:
            yield
        finally:
            self._batch_mode = False
            if self._pending_save_project:
                self._save_project_config()
                self._pending_save_project = False
            if self._pending_save_global:
                self._save_config()
                self._pending_save_global = False

    @staticmethod
    def _get_default_config_path() -> Path:
        """Get default config file path in user's app data directory."""
        import os

        app_data = Path(os.environ.get("APPDATA", Path.home() / ".config"))
        config_dir = app_data / APP_NAME
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                logger.info(f"Loaded config from {self._config_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config: {e}")
                self._config = {}
        else:
            self._config = {}

    def _save_config(self) -> None:
        """Save configuration to JSON file."""
        if self._batch_mode:
            self._pending_save_global = True
            return

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Saved config to {self._config_path}")
        except IOError as e:
            logger.exception(f"Failed to save config: {e}")
            raise

    def _load_project_config(self) -> None:
        """Load project-specific configuration from project.json in working folder."""
        if not self.working_folder:
            return

        project_config_path = self.working_folder / "project.json"
        if project_config_path.exists():
            try:
                with open(project_config_path, "r", encoding="utf-8") as f:
                    self._project_config = json.load(f)
                logger.info(f"Loaded project config from {project_config_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load project config: {e}")
                self._project_config = {}
        else:
            self._project_config = {}

    def _save_project_config(self) -> None:
        """Save project-specific configuration to project.json in working folder."""
        if self._batch_mode:
            self._pending_save_project = True
            return

        if not self.working_folder:
            return

        project_config_path = self.working_folder / "project.json"
        try:
            with open(project_config_path, "w", encoding="utf-8") as f:
                json.dump(self._project_config, f, indent=2)
            logger.info(f"Saved project config to {project_config_path}")
        except IOError as e:
            logger.exception(f"Failed to save project config: {e}")
            raise

    # --- API Key Management (Secure Storage) ---

    def get_api_key(self) -> Optional[str]:
        """Retrieve API key from Windows Credential Locker.

        Returns:
            The stored API key, or None if not set.
        """
        try:
            return keyring.get_password(APP_NAME, API_KEY_SERVICE)
        except keyring.errors.KeyringError as e:
            logger.exception(f"Failed to retrieve API key: {e}")
            return None

    def set_api_key(self, api_key: str) -> None:
        """Store API key in Windows Credential Locker.

        Args:
            api_key: The Gemini API key to store.
        """
        try:
            keyring.set_password(APP_NAME, API_KEY_SERVICE, api_key)
            logger.info("API key stored successfully")
        except keyring.errors.KeyringError as e:
            logger.exception(f"Failed to store API key: {e}")
            raise

    def delete_api_key(self) -> None:
        """Remove API key from Windows Credential Locker."""
        try:
            keyring.delete_password(APP_NAME, API_KEY_SERVICE)
            logger.info("API key deleted successfully")
        except keyring.errors.PasswordDeleteError:
            logger.warning("No API key to delete")
        except keyring.errors.KeyringError as e:
            logger.exception(f"Failed to delete API key: {e}")
            raise

    def has_api_key(self) -> bool:
        """Check if an API key is stored.

        Returns:
            True if an API key exists, False otherwise.
        """
        return self.get_api_key() is not None

    # --- Working Folder ---

    @property
    def working_folder(self) -> Optional[Path]:
        """Get the current working folder path."""
        folder = self._config.get("working_folder")
        return Path(folder) if folder else None

    @working_folder.setter
    def working_folder(self, path: Path) -> None:
        """Set the working folder path and create directory structure.

        Args:
            path: Path to the working folder.
        """
        self._config["working_folder"] = str(path)
        self._save_config()
        self._ensure_folder_structure(path)
        self._load_project_config()

    def _ensure_folder_structure(self, base_path: Path) -> None:
        """Create the required subdirectory structure in working folder."""
        # User requested only 3 visible folders.
        # We'll keep thumbnails in a hidden folder.
        subdirs = ["inputs", "references", "pages", ".thumbnails"]
        for subdir in subdirs:
            (base_path / subdir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created folder structure in {base_path}")

    # --- Aspect Ratio ---

    @property
    def aspect_ratio(self) -> str:
        """Get the current aspect ratio setting."""
        return self._project_config.get(
            "aspect_ratio", self._config.get("aspect_ratio", DEFAULT_ASPECT_RATIO)
        )

    @aspect_ratio.setter
    def aspect_ratio(self, ratio: str) -> None:
        """Set the aspect ratio.

        Args:
            ratio: Aspect ratio string (e.g., "3:4", "16:9").

        Raises:
            ValueError: If ratio is not in allowed values.
        """
        if ratio not in ASPECT_RATIOS:
            raise ValueError(
                f"Invalid aspect ratio: {ratio}. Must be one of {ASPECT_RATIOS}"
            )

        if self.working_folder:
            self._project_config["aspect_ratio"] = ratio
            self._save_project_config()
        else:
            self._config["aspect_ratio"] = ratio
            self._save_config()

    @property
    def character_sheet_aspect_ratio(self) -> Optional[str]:
        """Get the current character sheet aspect ratio setting.

        Returns:
            The aspect ratio string, or None if not set (meaning use page aspect ratio).
        """
        return self._project_config.get(
            "character_sheet_aspect_ratio",
            self._config.get("character_sheet_aspect_ratio"),
        )

    @character_sheet_aspect_ratio.setter
    def character_sheet_aspect_ratio(self, ratio: Optional[str]) -> None:
        """Set the character sheet aspect ratio.

        Args:
            ratio: Aspect ratio string (e.g., "3:4", "16:9") or None to unset.

        Raises:
            ValueError: If ratio is not None and not in allowed values.
        """
        if ratio is not None and ratio not in ASPECT_RATIOS:
            raise ValueError(
                f"Invalid aspect ratio: {ratio}. Must be one of {ASPECT_RATIOS} or None"
            )

        if self.working_folder:
            if ratio is None:
                self._project_config.pop("character_sheet_aspect_ratio", None)
            else:
                self._project_config["character_sheet_aspect_ratio"] = ratio
            self._save_project_config()
        else:
            if ratio is None:
                self._config.pop("character_sheet_aspect_ratio", None)
            else:
                self._config["character_sheet_aspect_ratio"] = ratio
            self._save_config()

    # --- Style Prompt ---

    @property
    def style_prompt(self) -> str:
        """Get the overarching style prompt for the book."""
        return self._project_config.get(
            "style_prompt", self._config.get("style_prompt", "")
        )

    @style_prompt.setter
    def style_prompt(self, prompt: str) -> None:
        """Set the style prompt.

        Args:
            prompt: The style description to prepend to all generation prompts.
        """
        if self.working_folder:
            self._project_config["style_prompt"] = prompt
            self._save_project_config()
        else:
            self._config["style_prompt"] = prompt
            self._save_config()

    # --- Generation Parameters ---

    @property
    def p_threshold(self) -> float:
        """Get the Top-P (nucleus sampling) value."""
        return self._project_config.get(
            "p_threshold", self._config.get("p_threshold", 0.95)
        )

    @p_threshold.setter
    def p_threshold(self, value: float) -> None:
        """Set the Top-P value."""
        if not (0.0 <= value <= 1.0):
            raise ValueError("Top-P must be between 0.0 and 1.0")

        if self.working_folder:
            self._project_config["p_threshold"] = value
            self._save_project_config()
        else:
            self._config["p_threshold"] = value
            self._save_config()

    @property
    def temperature(self) -> float:
        """Get the temperature value."""
        return self._project_config.get(
            "temperature", self._config.get("temperature", 1.0)
        )

    @temperature.setter
    def temperature(self, value: float) -> None:
        """Set the temperature value."""
        if not (0.0 <= value <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")

        if self.working_folder:
            self._project_config["temperature"] = value
            self._save_project_config()
        else:
            self._config["temperature"] = value
            self._save_config()

    # --- System Prompt Overrides ---

    def get_system_prompt_override(self, key: str) -> Optional[str]:
        """Get a project-specific system prompt override.

        Args:
            key: The system prompt key (e.g., "character_sheet", "page").

        Returns:
            The override prompt if set, or None to use default.
        """
        overrides = self._project_config.get("system_prompt_overrides", {})
        if isinstance(overrides, dict):
            value = overrides.get(key)
            if isinstance(value, str):
                return value
        return None

    def set_system_prompt_override(self, key: str, prompt: Optional[str]) -> None:
        """Set a project-specific system prompt override.

        Args:
            key: The system prompt key (e.g., "character_sheet", "page").
            prompt: The override prompt, or None/empty to clear the override.
        """
        if not self.working_folder:
            return

        if "system_prompt_overrides" not in self._project_config:
            self._project_config["system_prompt_overrides"] = {}

        if prompt and prompt.strip():
            self._project_config["system_prompt_overrides"][key] = prompt.strip()
        else:
            # Remove override if empty
            self._project_config["system_prompt_overrides"].pop(key, None)
            # Clean up empty dict
            if not self._project_config["system_prompt_overrides"]:
                del self._project_config["system_prompt_overrides"]

        self._save_project_config()

    def get_all_system_prompt_overrides(self) -> dict[str, str]:
        """Get all project-specific system prompt overrides.

        Returns:
            Dictionary of key -> override prompt.
        """
        overrides = self._project_config.get("system_prompt_overrides", {})
        if isinstance(overrides, dict):
            return {k: v for k, v in overrides.items() if isinstance(v, str)}
        return {}

    def clear_system_prompt_overrides(self) -> None:
        """Clear all system prompt overrides for this project."""
        if not self.working_folder:
            return

        if "system_prompt_overrides" in self._project_config:
            del self._project_config["system_prompt_overrides"]
            self._save_project_config()

    # --- Utility Methods ---

    def get_subfolder(self, name: str) -> Optional[Path]:
        """Get a subfolder path within the working folder.

        Args:
            name: Subfolder name (e.g., "inputs", "references", "pages").

        Returns:
            Full path to the subfolder, or None if working folder not set.
        """
        if self.working_folder:
            if name == "thumbnails":
                return self.working_folder / ".thumbnails"
            if name == "input":
                return self.working_folder / "inputs"
            return self.working_folder / name
        return None

    def is_configured(self) -> bool:
        """Check if the application is minimally configured.

        Returns:
            True if API key and working folder are set.
        """
        return self.has_api_key() and self.working_folder is not None

    def to_dict(self) -> dict:
        """Export current configuration as dictionary.

        Returns:
            Dictionary with all non-sensitive settings.
        """
        return {
            "working_folder": str(self.working_folder) if self.working_folder else None,
            "aspect_ratio": self.aspect_ratio,
            "character_sheet_aspect_ratio": self.character_sheet_aspect_ratio,
            "style_prompt": self.style_prompt,
            "p_threshold": self.p_threshold,
            "temperature": self.temperature,
            "has_api_key": self.has_api_key(),
        }

    # --- Gemini Usage Tracking ---

    def get_gemini_usage(self) -> dict:
        """Get persisted lifetime Gemini usage counters.

        Shape:
        {
          since: str|None,
          models: {
            <model>: {
              prompt_tokens, output_tokens, total_tokens,
              prompt_text_tokens, prompt_image_tokens,
              output_text_tokens, output_image_tokens,
              thoughts_tokens,
            }
          },
          cost: any|None,
          totals: { ... aggregated across models ... }
        }
        """
        raw = self._config.get(GEMINI_USAGE_KEY)
        if not isinstance(raw, dict):
            raw = {}

        models_raw = raw.get("models")
        if not isinstance(models_raw, dict):
            models_raw = {}

        def _model_defaults() -> dict:
            return {
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "prompt_text_tokens": 0,
                "prompt_image_tokens": 0,
                "output_text_tokens": 0,
                "output_image_tokens": 0,
                "thoughts_tokens": 0,
            }

        models: dict[str, dict] = {}
        for model_name, model_data in models_raw.items():
            if not isinstance(model_data, dict):
                continue
            if model_name not in SUPPORTED_GEMINI_MODELS:
                continue
            merged = _model_defaults()
            for key in list(merged.keys()):
                merged[key] = int(model_data.get(key, 0) or 0)
            models[str(model_name)] = merged

        totals = _model_defaults()
        for model_data in models.values():
            for key in totals:
                totals[key] += int(model_data.get(key, 0) or 0)

        return {
            "since": raw.get("since"),
            "models": models,
            "cost": raw.get("cost"),
            "totals": totals,
        }

    def reset_gemini_usage(self) -> None:
        """Reset lifetime Gemini usage counters and restart the clock."""
        self._config[GEMINI_USAGE_KEY] = {
            "since": _utc_now_iso(),
            "models": {},
            "cost": None,
        }
        self._save_config()

    def record_gemini_usage(
        self,
        *,
        model: str,
        prompt_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        prompt_text_tokens: Optional[int] = None,
        prompt_image_tokens: Optional[int] = None,
        output_text_tokens: Optional[int] = None,
        output_image_tokens: Optional[int] = None,
        thoughts_tokens: Optional[int] = None,
        cost=None,
    ) -> None:
        """Increment lifetime counters with values reported by the Gemini API."""
        if model not in SUPPORTED_GEMINI_MODELS:
            raise ValueError(
                f"Unsupported Gemini model for usage tracking: {model}. "
                f"Supported: {sorted(SUPPORTED_GEMINI_MODELS)}"
            )
        if (
            prompt_tokens is None
            and output_tokens is None
            and total_tokens is None
            and prompt_text_tokens is None
            and prompt_image_tokens is None
            and output_text_tokens is None
            and output_image_tokens is None
            and thoughts_tokens is None
            and cost is None
        ):
            return

        usage = self.get_gemini_usage()
        if not usage.get("since"):
            usage["since"] = _utc_now_iso()

        models = usage.get("models")
        if not isinstance(models, dict):
            models = {}
        model_usage = models.get(model)
        if not isinstance(model_usage, dict):
            model_usage = {
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "prompt_text_tokens": 0,
                "prompt_image_tokens": 0,
                "output_text_tokens": 0,
                "output_image_tokens": 0,
                "thoughts_tokens": 0,
            }

        def inc(key: str, value: Optional[int]) -> None:
            if value is None:
                return
            model_usage[key] = int(model_usage.get(key, 0) or 0) + int(value)

        inc("prompt_tokens", prompt_tokens)
        inc("output_tokens", output_tokens)
        if total_tokens is not None:
            inc("total_tokens", total_tokens)
        elif prompt_tokens is not None and output_tokens is not None:
            inc("total_tokens", int(prompt_tokens) + int(output_tokens))

        inc("prompt_text_tokens", prompt_text_tokens)
        inc("prompt_image_tokens", prompt_image_tokens)
        inc("output_text_tokens", output_text_tokens)
        inc("output_image_tokens", output_image_tokens)
        inc("thoughts_tokens", thoughts_tokens)

        models[model] = model_usage
        usage["models"] = models

        # Only store cost if API provided it. We do not attempt to compute or
        # aggregate monetary values with unknown schema.
        if cost is not None:
            usage["cost"] = cost

        self._config[GEMINI_USAGE_KEY] = usage
        self._save_config()
