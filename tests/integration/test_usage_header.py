"""Integration tests for the Gemini usage metrics header UI."""

import pytest
from unittest.mock import MagicMock, patch

from nicegui.testing import User


@pytest.fixture
def mock_settings_with_usage(temp_dir):
    with patch("src.services.settings.Settings") as MockSettings:
        settings = MagicMock()
        settings.get_api_key.return_value = ""
        settings.working_folder = temp_dir
        settings.aspect_ratio = "3:4"
        settings.style_prompt = ""
        settings.get_gemini_usage.return_value = {
            "since": None,
            "models": {},
            "totals": {
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "prompt_text_tokens": 0,
                "prompt_image_tokens": 0,
                "output_text_tokens": 0,
                "output_image_tokens": 0,
                "thoughts_tokens": 0,
            },
            "cost": None,
        }
        MockSettings.return_value = settings
        yield settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_header_shows_usage_and_pricing_link(
    user: User, mock_settings_with_usage
):
    await user.open("/")

    await user.should_see("Tokens:")
    await user.should_see("Pricing")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_header_has_reset_button(user: User, mock_settings_with_usage):
    await user.open("/")
    # Material icons are often rendered as text ligatures
    await user.should_see("restart_alt")
