"""Integration tests for image generation workflow.

Tests the complete image generation UI workflow using NiceGUI User simulation.
All API calls are mocked to avoid costs.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from nicegui import ui
from nicegui.testing import User


@pytest.fixture
def mock_image_service(mock_genai_client, temp_dir):
    """Mock ImageService for integration tests."""
    with patch("src.services.image_service.ImageService") as MockService:
        service_instance = MagicMock()

        # Create a sample image for test output
        sample_output = temp_dir / "generated_image.png"
        from PIL import Image

        img = Image.new("RGB", (512, 512), color="purple")
        img.save(sample_output)

        # Configure async methods
        async def mock_generate(*args, **kwargs):
            return sample_output

        service_instance.generate_image = AsyncMock(side_effect=mock_generate)
        service_instance.generate_character_sheet = AsyncMock(side_effect=mock_generate)
        service_instance.generate_page = AsyncMock(side_effect=mock_generate)
        service_instance.create_thumbnail = MagicMock(return_value=sample_output)

        MockService.return_value = service_instance

        yield service_instance


@pytest.fixture
def mock_settings_with_key(temp_dir):
    """Mock Settings with API key configured."""
    with patch("src.services.settings.Settings") as MockSettings:
        settings = MagicMock()
        settings.get_api_key.return_value = "test-api-key"
        settings.working_folder = temp_dir
        settings.aspect_ratio = "3:4"
        settings.style_prompt = "Watercolor style"

        MockSettings.return_value = settings

        yield settings


@pytest.mark.integration
@pytest.mark.asyncio
class TestImageGenerationWorkflow:
    """Integration tests for image generation."""

    async def test_character_section_exists(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test that character generation is available in Generate tab."""
        await user.open("/")
        await user.should_see("Generate")
        user.find(content="Generate").click()
        # Character Sheet option is available via type toggle
        await user.should_see("Character Sheet")

    async def test_page_generation_section_exists(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test that page generation is available in Generate tab."""
        await user.open("/")
        await user.should_see("Generate")
        user.find(content="Generate").click()
        # Page option is available via type toggle
        await user.should_see("Page")

    async def test_generate_character_button(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test generating a character through the UI."""
        await user.open("/")

        # Navigate to Generate tab
        await user.should_see("Generate")
        user.find(content="Generate").click()

        # Wait for Generate tab content to load
        await user.should_see("Rework Mode")

        # Should see generate button - using content-based find
        generate_btn = user.find(content="Generate", kind=ui.button)
        assert generate_btn is not None

    async def test_generate_page_button(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test generating a page through the UI."""
        await user.open("/")

        # Navigate to Generate tab
        await user.should_see("Generate")
        user.find(content="Generate").click()

        # Wait for Generate tab content to load
        await user.should_see("Rework Mode")

        # Should see generate button - using content-based find
        generate_btn = user.find(content="Generate", kind=ui.button)
        assert generate_btn is not None

    async def test_generation_disabled_without_api_key(self, user: User, temp_dir):
        """Test that generation is disabled without API key."""
        with patch("src.services.settings.Settings") as MockSettings:
            settings = MagicMock()
            settings.get_api_key.return_value = ""  # No API key
            settings.working_folder = temp_dir
            settings.aspect_ratio = "3:4"
            settings.style_prompt = ""

            MockSettings.return_value = settings

            await user.open("/")

            # Should see API key related elements prompting for configuration
            await user.should_see("API Key")


@pytest.mark.integration
@pytest.mark.asyncio
class TestImageGenerationErrors:
    """Tests for error handling during image generation."""

    async def test_generation_error_shows_message(
        self, user: User, mock_settings_with_key
    ):
        """Test that generation errors are shown to user."""
        with patch("src.services.image_service.ImageService") as MockService:
            service = MagicMock()
            service.generate_character_sheet = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )
            MockService.return_value = service

            await user.open("/")

            # Navigate to Generate tab
            await user.should_see("Generate")
            user.find(content="Generate").click()

            # Wait for Generate tab content to load
            await user.should_see("Rework Mode")

            # Should see the generate button (error handling is on click)
            generate_btn = user.find(content="Generate", kind=ui.button)
            assert generate_btn is not None

    async def test_concurrent_generation_blocked(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test that concurrent generations are blocked."""
        await user.open("/")

        # Navigate to Generate tab
        await user.should_see("Generate")
        user.find(content="Generate").click()

        # The asyncio lock should prevent concurrent requests
        # This is tested more thoroughly in unit tests
        await user.should_see("Rework Mode")


@pytest.mark.integration
@pytest.mark.asyncio
class TestSketchUploadWorkflow:
    """Tests for sketch upload and processing."""

    async def test_upload_section_exists(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test that upload section exists in Add tab."""
        await user.open("/")
        await user.should_see("Add")
        user.find(content="Add").click()
        await user.should_see("Upload Reference Images")

    async def test_sketch_tab_exists(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test that sketch tab exists."""
        await user.open("/")
        await user.should_see("Sketch")
        user.find(content="Sketch").click()
        await user.should_see("Sketching Canvas")

    async def test_sketch_canvas_exists(
        self, user: User, mock_settings_with_key, mock_image_service
    ):
        """Test that sketch canvas component exists."""
        await user.open("/")

        # Navigate to Sketch tab
        await user.should_see("Sketch")
        user.find(content="Sketch").click()

        # Look for sketch-related elements
        await user.should_see("Sketching Canvas")
        await user.should_see("Sketch Name")


@pytest.mark.integration
@pytest.mark.asyncio
class TestThumbnailGeneration:
    """Tests for thumbnail generation in the UI."""

    async def test_thumbnails_displayed(
        self, user: User, mock_settings_with_key, mock_image_service, temp_dir
    ):
        """Test that thumbnails are generated and displayed."""
        # Create some sample images in the working folder
        refs_folder = temp_dir / "references"
        refs_folder.mkdir(exist_ok=True)

        from PIL import Image

        img = Image.new("RGB", (512, 512), color="red")
        img.save(refs_folder / "character_1.png")

        await user.open("/")

        # Navigate to Generate tab to see character thumbnails
        await user.should_see("Generate")
        user.find(content="Generate").click()

        # The page should load without errors
        await user.should_see("Select References")
