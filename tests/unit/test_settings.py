"""Unit tests for the Settings service."""

import json
import pytest
from pathlib import Path

from src.services.settings import (
    Settings,
    APP_NAME,
    API_KEY_SERVICE,
    ASPECT_RATIOS,
)


@pytest.mark.unit
class TestSettings:
    """Tests for the Settings class."""

    def test_init_creates_default_config(self, config_path: Path):
        """Test that Settings initializes with empty config if none exists."""
        settings = Settings(config_path)

        assert settings.working_folder is None
        assert settings.aspect_ratio == "3:4"  # Default
        assert settings.style_prompt == ""

    def test_init_loads_existing_config(self, config_path: Path):
        """Test that Settings loads existing config file."""
        # Create config file
        config_data = {
            "working_folder": "C:/test/folder",
            "aspect_ratio": "16:9",
            "style_prompt": "Test style",
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        settings = Settings(config_path)

        assert settings.working_folder == Path("C:/test/folder")
        assert settings.aspect_ratio == "16:9"
        assert settings.style_prompt == "Test style"

    def test_working_folder_setter_creates_structure(
        self, config_path: Path, temp_dir: Path
    ):
        """Test that setting working folder creates subdirectory structure."""
        settings = Settings(config_path)
        working = temp_dir / "my_project"

        settings.working_folder = working

        assert working.exists()
        assert (working / "inputs").exists()
        assert (working / "references").exists()
        assert (working / "pages").exists()
        assert (working / ".thumbnails").exists()
        # These should NOT exist
        assert not (working / "characters").exists()
        assert not (working / "sketches").exists()
        assert not (working / "exports").exists()

    def test_working_folder_persists(self, config_path: Path, temp_dir: Path):
        """Test that working folder is saved to config file."""
        settings = Settings(config_path)
        working = temp_dir / "my_project"

        settings.working_folder = working

        # Reload settings
        settings2 = Settings(config_path)
        assert settings2.working_folder == working

    def test_aspect_ratio_valid_values(self, config_path: Path):
        """Test that valid aspect ratios are accepted."""
        settings = Settings(config_path)

        for ratio in ASPECT_RATIOS:
            settings.aspect_ratio = ratio
            assert settings.aspect_ratio == ratio

    def test_aspect_ratio_invalid_value_raises(self, config_path: Path):
        """Test that invalid aspect ratio raises ValueError."""
        settings = Settings(config_path)

        with pytest.raises(ValueError, match="Invalid aspect ratio"):
            settings.aspect_ratio = "invalid"

    def test_style_prompt_setter(self, config_path: Path):
        """Test setting and getting style prompt."""
        settings = Settings(config_path)

        settings.style_prompt = "Watercolor children's book style"

        assert settings.style_prompt == "Watercolor children's book style"

    def test_get_subfolder(self, config_path: Path, temp_dir: Path):
        """Test getting subfolder paths."""
        settings = Settings(config_path)
        working = temp_dir / "my_project"
        settings.working_folder = working

        assert settings.get_subfolder("input") == working / "inputs"
        assert settings.get_subfolder("pages") == working / "pages"

    def test_get_subfolder_returns_none_without_working_folder(self, config_path: Path):
        """Test that get_subfolder returns None if working folder not set."""
        settings = Settings(config_path)

        assert settings.get_subfolder("input") is None

    def test_to_dict(self, config_path: Path, temp_dir: Path, mock_keyring):
        """Test exporting settings to dictionary."""
        mock_kr, stored = mock_keyring
        settings = Settings(config_path)
        working = temp_dir / "my_project"
        settings.working_folder = working
        settings.aspect_ratio = "4:3"
        settings.style_prompt = "Test"

        result = settings.to_dict()

        assert result["working_folder"] == str(working)
        assert result["aspect_ratio"] == "4:3"
        assert result["style_prompt"] == "Test"
        assert "has_api_key" in result

    def test_gemini_usage_defaults(self, config_path: Path):
        settings = Settings(config_path)

        usage = settings.get_gemini_usage()

        assert usage["since"] is None
        assert usage["models"] == {}
        assert usage["totals"]["prompt_tokens"] == 0
        assert usage["totals"]["output_tokens"] == 0
        assert usage["totals"]["total_tokens"] == 0
        assert usage["totals"]["prompt_text_tokens"] == 0
        assert usage["totals"]["prompt_image_tokens"] == 0
        assert usage["totals"]["output_text_tokens"] == 0
        assert usage["totals"]["output_image_tokens"] == 0
        assert usage["totals"]["thoughts_tokens"] == 0
        assert usage["cost"] is None

    def test_record_and_reset_gemini_usage(self, config_path: Path):
        settings = Settings(config_path)

        model = "gemini-3-pro-image-preview"
        settings.record_gemini_usage(
            model=model, prompt_tokens=3, output_tokens=7, total_tokens=10
        )
        usage = settings.get_gemini_usage()

        assert usage["since"] is not None
        assert usage["models"][model]["prompt_tokens"] == 3
        assert usage["models"][model]["output_tokens"] == 7
        assert usage["models"][model]["total_tokens"] == 10
        assert usage["totals"]["prompt_tokens"] == 3
        assert usage["totals"]["output_tokens"] == 7
        assert usage["totals"]["total_tokens"] == 10

        settings.record_gemini_usage(model=model, prompt_tokens=1, output_tokens=2)
        usage = settings.get_gemini_usage()
        assert usage["models"][model]["prompt_tokens"] == 4
        assert usage["models"][model]["output_tokens"] == 9
        assert usage["models"][model]["total_tokens"] == 13
        assert usage["totals"]["prompt_tokens"] == 4
        assert usage["totals"]["output_tokens"] == 9
        assert usage["totals"]["total_tokens"] == 13

        settings.reset_gemini_usage()
        usage = settings.get_gemini_usage()

        assert usage["since"] is not None
        assert usage["models"] == {}
        assert usage["totals"]["prompt_tokens"] == 0
        assert usage["totals"]["output_tokens"] == 0
        assert usage["totals"]["total_tokens"] == 0
        assert usage["cost"] is None

    def test_record_gemini_usage_unsupported_model_raises(self, config_path: Path):
        settings = Settings(config_path)

        with pytest.raises(ValueError, match="Unsupported Gemini model"):
            settings.record_gemini_usage(model="gemini-2.0-flash-exp", prompt_tokens=1)


@pytest.mark.unit
class TestSettingsApiKey:
    """Tests for API key management in Settings."""

    def test_set_api_key(self, config_path: Path, mock_keyring):
        """Test storing API key."""
        mock_kr, stored = mock_keyring
        settings = Settings(config_path)

        settings.set_api_key("test-api-key-12345")

        mock_kr.set_password.assert_called_once_with(
            APP_NAME, API_KEY_SERVICE, "test-api-key-12345"
        )

    def test_get_api_key(self, config_path: Path, mock_keyring):
        """Test retrieving API key."""
        mock_kr, stored = mock_keyring
        stored[(APP_NAME, API_KEY_SERVICE)] = "my-secret-key"
        settings = Settings(config_path)

        result = settings.get_api_key()

        assert result == "my-secret-key"

    def test_has_api_key_true(self, config_path: Path, mock_keyring):
        """Test has_api_key returns True when key exists."""
        mock_kr, stored = mock_keyring
        stored[(APP_NAME, API_KEY_SERVICE)] = "my-key"
        settings = Settings(config_path)

        assert settings.has_api_key() is True

    def test_has_api_key_false(self, config_path: Path, mock_keyring):
        """Test has_api_key returns False when key doesn't exist."""
        mock_kr, stored = mock_keyring
        settings = Settings(config_path)

        assert settings.has_api_key() is False

    def test_delete_api_key(self, config_path: Path, mock_keyring):
        """Test deleting API key."""
        mock_kr, stored = mock_keyring
        stored[(APP_NAME, API_KEY_SERVICE)] = "my-key"
        settings = Settings(config_path)

        settings.delete_api_key()

        mock_kr.delete_password.assert_called_once_with(APP_NAME, API_KEY_SERVICE)

    def test_is_configured_true(self, config_path: Path, temp_dir: Path, mock_keyring):
        """Test is_configured returns True when fully configured."""
        mock_kr, stored = mock_keyring
        stored[(APP_NAME, API_KEY_SERVICE)] = "my-key"
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        assert settings.is_configured() is True

    def test_is_configured_false_no_key(
        self, config_path: Path, temp_dir: Path, mock_keyring
    ):
        """Test is_configured returns False without API key."""
        mock_kr, stored = mock_keyring
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        assert settings.is_configured() is False

    def test_is_configured_false_no_folder(self, config_path: Path, mock_keyring):
        """Test is_configured returns False without working folder."""
        mock_kr, stored = mock_keyring
        stored[(APP_NAME, API_KEY_SERVICE)] = "my-key"
        settings = Settings(config_path)

        assert settings.is_configured() is False


@pytest.mark.unit
class TestSystemPromptOverrides:
    """Tests for system prompt override functionality."""

    def test_get_override_returns_none_when_not_set(
        self, config_path: Path, temp_dir: Path
    ):
        """Test that get_system_prompt_override returns None when no override is set."""
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        assert settings.get_system_prompt_override("character_sheet") is None
        assert settings.get_system_prompt_override("page") is None

    def test_set_and_get_override(self, config_path: Path, temp_dir: Path):
        """Test setting and getting a system prompt override."""
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        settings.set_system_prompt_override(
            "character_sheet", "Custom character prompt"
        )

        assert (
            settings.get_system_prompt_override("character_sheet")
            == "Custom character prompt"
        )
        assert settings.get_system_prompt_override("page") is None

    def test_set_override_persists_to_project_json(
        self, config_path: Path, temp_dir: Path
    ):
        """Test that overrides are persisted to project.json."""
        settings = Settings(config_path)
        project_dir = temp_dir / "project"
        settings.working_folder = project_dir

        settings.set_system_prompt_override("page", "Custom page prompt")

        # Reload settings and check override persisted
        settings2 = Settings(config_path)
        settings2._load_project_config()
        assert settings2.get_system_prompt_override("page") == "Custom page prompt"

    def test_clear_override_with_empty_string(self, config_path: Path, temp_dir: Path):
        """Test that setting empty string clears the override."""
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        settings.set_system_prompt_override("character_sheet", "Custom prompt")
        assert settings.get_system_prompt_override("character_sheet") == "Custom prompt"

        settings.set_system_prompt_override("character_sheet", "")
        assert settings.get_system_prompt_override("character_sheet") is None

    def test_clear_override_with_none(self, config_path: Path, temp_dir: Path):
        """Test that setting None clears the override."""
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        settings.set_system_prompt_override("page", "Custom prompt")
        settings.set_system_prompt_override("page", None)

        assert settings.get_system_prompt_override("page") is None

    def test_get_all_overrides(self, config_path: Path, temp_dir: Path):
        """Test getting all system prompt overrides."""
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        settings.set_system_prompt_override("character_sheet", "Char prompt")
        settings.set_system_prompt_override("page", "Page prompt")

        all_overrides = settings.get_all_system_prompt_overrides()

        assert all_overrides == {
            "character_sheet": "Char prompt",
            "page": "Page prompt",
        }

    def test_clear_all_overrides(self, config_path: Path, temp_dir: Path):
        """Test clearing all system prompt overrides."""
        settings = Settings(config_path)
        settings.working_folder = temp_dir / "project"

        settings.set_system_prompt_override("character_sheet", "Char prompt")
        settings.set_system_prompt_override("page", "Page prompt")

        settings.clear_system_prompt_overrides()

        assert settings.get_all_system_prompt_overrides() == {}
        assert settings.get_system_prompt_override("character_sheet") is None
        assert settings.get_system_prompt_override("page") is None

    def test_override_without_working_folder_is_noop(self, config_path: Path):
        """Test that setting override without working folder does nothing."""
        settings = Settings(config_path)

        settings.set_system_prompt_override("character_sheet", "Custom prompt")

        assert settings.get_system_prompt_override("character_sheet") is None

    def test_character_sheet_aspect_ratio_default(self, config_path: Path):
        """Test that character sheet aspect ratio defaults to None."""
        settings = Settings(config_path)
        assert settings.character_sheet_aspect_ratio is None

    def test_character_sheet_aspect_ratio_setter(self, config_path: Path):
        """Test setting and getting character sheet aspect ratio."""
        settings = Settings(config_path)

        settings.character_sheet_aspect_ratio = "16:9"
        assert settings.character_sheet_aspect_ratio == "16:9"

        settings.character_sheet_aspect_ratio = None
        assert settings.character_sheet_aspect_ratio is None

    def test_character_sheet_aspect_ratio_invalid(self, config_path: Path):
        """Test that invalid character sheet aspect ratio raises ValueError."""
        settings = Settings(config_path)

        with pytest.raises(ValueError, match="Invalid aspect ratio"):
            settings.character_sheet_aspect_ratio = "invalid"
