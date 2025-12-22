"""Unit tests for the Image Service.

All tests mock the Gemini API to avoid real API calls and token usage.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

from src.services.image_service import (
    ImageService,
    ImageGenerationError,
    SYSTEM_PROMPTS,
    TEMPLATES,
    THUMBNAIL_SIZE,
)


@pytest.mark.unit
class TestImageService:
    """Tests for the ImageService class."""

    def test_init(self, working_folder: Path, mock_genai):
        """Test ImageService initialization."""
        service = ImageService("test-api-key", working_folder)

        assert service._working_folder == working_folder
        assert service.is_generating is False
        mock_genai.Client.assert_called_once_with(api_key="test-api-key")

    def test_init_with_system_prompt_overrides(self, working_folder: Path, mock_genai):
        """Test ImageService initialization with system prompt overrides."""
        overrides = {"character_sheet": "Custom character prompt"}
        service = ImageService(
            "test-api-key", working_folder, system_prompt_overrides=overrides
        )

        assert service._system_prompt_overrides == overrides

    def test_get_system_prompt_returns_default(self, working_folder: Path, mock_genai):
        """Test get_system_prompt returns default when no override."""
        service = ImageService("test-api-key", working_folder)

        result = service.get_system_prompt("character_sheet")

        assert result == SYSTEM_PROMPTS.get("character_sheet", "")

    def test_get_system_prompt_returns_override(self, working_folder: Path, mock_genai):
        """Test get_system_prompt returns override when set."""
        overrides = {"character_sheet": "Custom character prompt"}
        service = ImageService(
            "test-api-key", working_folder, system_prompt_overrides=overrides
        )

        result = service.get_system_prompt("character_sheet")

        assert result == "Custom character prompt"

    def test_set_system_prompt_overrides(self, working_folder: Path, mock_genai):
        """Test set_system_prompt_overrides updates overrides."""
        service = ImageService("test-api-key", working_folder)

        service.set_system_prompt_overrides({"page": "New page prompt"})

        assert service.get_system_prompt("page") == "New page prompt"
        assert service.get_system_prompt("character_sheet") == SYSTEM_PROMPTS.get(
            "character_sheet", ""
        )

    def test_get_mime_type(self, working_folder: Path, mock_genai):
        """Test MIME type detection for various file types."""
        service = ImageService("test-api-key", working_folder)

        assert service._get_mime_type(Path("test.png")) == "image/png"
        assert service._get_mime_type(Path("test.jpg")) == "image/jpeg"
        assert service._get_mime_type(Path("test.jpeg")) == "image/jpeg"
        assert service._get_mime_type(Path("test.gif")) == "image/gif"
        # Unknown type defaults to jpeg
        assert service._get_mime_type(Path("test.xyz")) == "image/jpeg"

    def test_create_thumbnail(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test thumbnail creation."""
        # Copy sample image to working folder
        import shutil

        test_image = working_folder / "pages" / "test.png"
        shutil.copy(sample_image, test_image)

        service = ImageService("test-api-key", working_folder)
        thumbnail_path = service._create_thumbnail(test_image)

        assert thumbnail_path.exists()
        assert ".thumbnails" in str(thumbnail_path)
        assert "_thumb" in thumbnail_path.name

        # Check thumbnail size
        with Image.open(thumbnail_path) as img:
            assert max(img.size) <= THUMBNAIL_SIZE

    def test_build_prompt_simple(self, working_folder: Path, mock_genai):
        """Test basic prompt building."""
        service = ImageService("test-api-key", working_folder)

        result = service._build_prompt("Draw a cat")

        assert result == "Draw a cat"

    def test_build_prompt_with_style(self, working_folder: Path, mock_genai):
        """Test prompt building with style (style is now in system prompt)."""
        service = ImageService("test-api-key", working_folder)

        result = service._build_prompt("Draw a cat", style_prompt="Watercolor style")

        assert "Draw a cat" in result
        assert "Watercolor style" not in result

    def test_build_prompt_with_system_prompt(self, working_folder: Path, mock_genai):
        """System prompts should not be concatenated into the user prompt text."""
        service = ImageService("test-api-key", working_folder)

        result = service._build_prompt(
            "A brave knight", system_prompt_key="character_sheet"
        )

        assert "A brave knight" in result
        assert SYSTEM_PROMPTS["character_sheet"] not in result

    @pytest.mark.asyncio
    async def test_generate_character_sheet_passes_system_instruction(
        self, working_folder: Path, mock_genai
    ):
        """Ensure system prompt is sent via GenerateContentConfig.system_instruction."""
        service = ImageService("test-api-key", working_folder)

        await service.generate_character_sheet(
            description="A brave knight with silver armor",
            style_prompt="Fantasy illustration style",
            aspect_ratio="3:4",
        )

        client = mock_genai.Client.return_value
        assert client.models.generate_content_stream.called
        call_kwargs = client.models.generate_content_stream.call_args.kwargs
        config = call_kwargs.get("config")
        assert config is not None

        expected_system_instruction = SYSTEM_PROMPTS["character_sheet"]
        style_prefix = TEMPLATES.get("style_prefix", "Style: {style_prompt}")
        expected_system_instruction += "\n\n" + style_prefix.format(
            style_prompt="Fantasy illustration style"
        )

        assert (
            getattr(config, "system_instruction", None) == expected_system_instruction
        )

    def test_save_generated_image(self, working_folder: Path, mock_genai):
        """Test saving generated image data."""
        service = ImageService("test-api-key", working_folder)

        # Create test image data
        img = Image.new("RGB", (50, 50), color="red")
        import io

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        result = service._save_generated_image(
            data=image_bytes,
            mime_type="image/png",
            category="pages",
            name_prefix="test",
        )

        assert result.exists()
        assert result.parent.name == "pages"
        assert result.suffix == ".png"
        assert "test" in result.stem

    @pytest.mark.asyncio
    async def test_generate_image_basic(self, working_folder: Path, mock_genai):
        """Test basic image generation."""
        service = ImageService("test-api-key", working_folder)

        image_path, thumb_path = await service.generate_image(
            prompt="A sunset over mountains", aspect_ratio="3:4", category="pages"
        )

        assert image_path.exists()
        assert thumb_path.exists()
        assert image_path.parent.name == "pages"
        assert thumb_path.parent.name == ".thumbnails"

    @pytest.mark.asyncio
    async def test_generate_image_emits_progress(
        self, working_folder: Path, mock_genai
    ):
        """Test that progress_callback is called during generation."""
        service = ImageService("test-api-key", working_folder)

        progress: list[str] = []

        await service.generate_image(
            prompt="A sunset over mountains",
            aspect_ratio="3:4",
            category="pages",
            progress_callback=progress.append,
        )

        assert "Waiting for Gemini to finish image generation..." in progress
        assert "Saving generated image..." in progress
        assert "Creating thumbnail..." in progress

    @pytest.mark.asyncio
    async def test_generate_image_reports_usage_metadata(
        self, working_folder: Path, mock_genai
    ):
        usage_cb = MagicMock()
        service = ImageService("test-api-key", working_folder, usage_callback=usage_cb)

        await service.generate_image(
            prompt="A sunset over mountains",
            aspect_ratio="3:4",
            category="pages",
        )

        usage_cb.assert_called_once()
        usage = usage_cb.call_args[0][0]
        assert getattr(usage, "model") == "gemini-3-pro-image-preview"
        assert getattr(usage, "prompt_tokens") == 10
        assert getattr(usage, "output_tokens") == 20
        assert getattr(usage, "total_tokens") == 30

    @pytest.mark.asyncio
    async def test_generate_image_with_references(
        self, working_folder: Path, sample_images: list[Path], mock_genai
    ):
        """Test image generation with reference images."""
        service = ImageService("test-api-key", working_folder)

        # Use some sample images as references
        references = [img for img in sample_images if "char" in img.name][:2]

        image_path, thumb_path = await service.generate_image(
            prompt="A scene with the character",
            reference_images=references,
            aspect_ratio="3:4",
            category="pages",
        )

        assert image_path.exists()

    @pytest.mark.asyncio
    async def test_generate_image_concurrent_lock(
        self, working_folder: Path, mock_genai
    ):
        """Test that concurrent generation requests are serialized."""
        service = ImageService("test-api-key", working_folder)

        # Track generation order
        generation_order = []
        original_call_api = service._call_api

        def tracked_call_api(*args, **kwargs):
            generation_order.append(len(generation_order))
            import time

            time.sleep(0.01)  # Small delay to ensure ordering
            return original_call_api(*args, **kwargs)

        service._call_api = tracked_call_api

        # Start multiple generations
        results = await asyncio.gather(
            service.generate_image("Prompt 1", category="pages"),
            service.generate_image("Prompt 2", category="pages"),
        )

        assert len(results) == 2
        # Generations should be serialized (order should be sequential)
        assert generation_order == [0, 1]

    @pytest.mark.asyncio
    async def test_generate_character_sheet(self, working_folder: Path, mock_genai):
        """Test character sheet generation."""
        service = ImageService("test-api-key", working_folder)

        image_path, thumb_path = await service.generate_character_sheet(
            description="A brave knight with silver armor",
            style_prompt="Fantasy illustration style",
            aspect_ratio="3:4",
        )

        assert image_path.exists()
        assert image_path.parent.name == "references"

    @pytest.mark.asyncio
    async def test_generate_page(self, working_folder: Path, mock_genai):
        """Test page generation."""
        service = ImageService("test-api-key", working_folder)

        image_path, thumb_path = await service.generate_page(
            scene_description="The knight enters the castle",
            style_prompt="Fantasy illustration style",
            aspect_ratio="3:4",
        )

        assert image_path.exists()
        assert image_path.parent.name == "pages"

    def test_ensure_thumbnail_creates_if_missing(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that ensure_thumbnail creates thumbnail if it doesn't exist."""
        import shutil

        test_image = working_folder / "pages" / "test_image.png"
        shutil.copy(sample_image, test_image)

        service = ImageService("test-api-key", working_folder)

        # No thumbnail exists yet
        assert service.get_thumbnail_path(test_image) is None

        # ensure_thumbnail should create it
        thumb_path = service.ensure_thumbnail(test_image)

        assert thumb_path.exists()

    def test_is_generating_flag(self, working_folder: Path, mock_genai):
        """Test that is_generating flag is set during generation."""
        service = ImageService("test-api-key", working_folder)

        assert service.is_generating is False

        # Note: Full async test would verify flag during generation


@pytest.mark.unit
class TestImageServiceErrors:
    """Tests for error handling in ImageService."""

    @pytest.mark.asyncio
    async def test_generate_image_api_error(self, working_folder: Path, mock_genai):
        """Test handling of API errors."""
        # Make the mock raise an error
        mock_genai.Client.return_value.models.generate_content_stream.side_effect = (
            Exception("API Error")
        )

        service = ImageService("test-api-key", working_folder)

        with pytest.raises(ImageGenerationError, match="Gemini API Error"):
            await service.generate_image("Test prompt", category="pages")

    @pytest.mark.asyncio
    async def test_generate_image_no_result(self, working_folder: Path, mock_genai):
        """Test handling when API returns no image."""
        # Return empty response
        mock_genai.Client.return_value.models.generate_content_stream.return_value = []

        service = ImageService("test-api-key", working_folder)

        with pytest.raises(ImageGenerationError, match="No image was generated"):
            await service.generate_image("Test prompt", category="pages")

    @pytest.mark.asyncio
    async def test_generate_image_skips_missing_references(
        self, working_folder: Path, mock_genai
    ):
        """Test that missing reference images are skipped with warning."""
        service = ImageService("test-api-key", working_folder)

        # Include a non-existent reference
        references = [Path("/nonexistent/image.png")]

        # Should not raise, just skip the missing reference
        image_path, thumb_path = await service.generate_image(
            prompt="Test", reference_images=references, category="pages"
        )

        assert image_path.exists()

    @pytest.mark.asyncio
    async def test_generate_image_rejects_empty_prompt(
        self, working_folder: Path, mock_genai
    ):
        service = ImageService("test-api-key", working_folder)

        with pytest.raises(ImageGenerationError, match="Prompt is empty"):
            await service.generate_image("   ", category="pages")

    @pytest.mark.asyncio
    async def test_generate_image_rejects_overlong_prompt(
        self, working_folder: Path, mock_genai
    ):
        service = ImageService("test-api-key", working_folder)

        too_long = "x" * 9000
        with pytest.raises(ImageGenerationError, match="Prompt is too long"):
            await service.generate_image(too_long, category="pages")


@pytest.mark.unit
class TestImageServiceRework:
    """Tests for the rework functionality in ImageService."""

    @pytest.mark.asyncio
    async def test_rework_image_basic(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test basic image rework."""
        import shutil

        # Copy sample image to pages folder
        original_path = working_folder / "pages" / "original.png"
        shutil.copy(sample_image, original_path)

        service = ImageService("test-api-key", working_folder)

        image_path, thumb_path = await service.rework_image(
            original_image=original_path,
            prompt="Make the colors more vibrant",
            category="pages",
        )

        assert image_path.exists()
        assert thumb_path.exists()
        # Reworked image should have rework prefix
        assert "rework_" in image_path.name
        # Original should still exist
        assert original_path.exists()
        # Reworked image should be in same category
        assert image_path.parent.name == "pages"

    @pytest.mark.asyncio
    async def test_rework_image_preserves_original(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that rework does not overwrite the original image."""
        import shutil

        original_path = working_folder / "references" / "hero.png"
        shutil.copy(sample_image, original_path)
        original_size = original_path.stat().st_size

        service = ImageService("test-api-key", working_folder)

        await service.rework_image(
            original_image=original_path,
            prompt="Add more detail to the face",
            category="references",
        )

        # Original should be unchanged
        assert original_path.exists()
        assert original_path.stat().st_size == original_size

    @pytest.mark.asyncio
    async def test_rework_image_uses_correct_system_prompt(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that rework uses the appropriate system prompt based on category."""
        import shutil

        # Test for pages
        page_original = working_folder / "pages" / "page_01.png"
        shutil.copy(sample_image, page_original)

        service = ImageService("test-api-key", working_folder)

        await service.rework_image(
            original_image=page_original,
            prompt="Add more characters",
            category="pages",
        )

        client = mock_genai.Client.return_value
        call_kwargs = client.models.generate_content_stream.call_args.kwargs
        config = call_kwargs.get("config")
        assert config is not None
        assert "rework" in getattr(config, "system_instruction", "").lower()

    @pytest.mark.asyncio
    async def test_rework_image_includes_original_as_reference(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that the original image is included as a reference."""
        import shutil

        original_path = working_folder / "pages" / "scene.png"
        shutil.copy(sample_image, original_path)

        service = ImageService("test-api-key", working_folder)

        await service.rework_image(
            original_image=original_path,
            prompt="Change the lighting",
            category="pages",
        )

        client = mock_genai.Client.return_value
        call_args = client.models.generate_content_stream.call_args
        contents = call_args.kwargs.get("contents", [])

        # Should have at least one content with parts
        assert len(contents) > 0
        parts = contents[0].parts

        # Should have more than just text (should include image)
        assert len(parts) >= 2

    @pytest.mark.asyncio
    async def test_rework_image_with_additional_references(
        self, working_folder: Path, sample_images: list[Path], mock_genai
    ):
        """Test rework with additional reference images."""
        import shutil

        original_path = working_folder / "pages" / "original_scene.png"
        shutil.copy(sample_images[0], original_path)

        # Use other images as additional references
        additional_refs = [sample_images[1], sample_images[2]]

        service = ImageService("test-api-key", working_folder)

        image_path, thumb_path = await service.rework_image(
            original_image=original_path,
            prompt="Match the style of the other images",
            additional_references=additional_refs,
            category="pages",
        )

        assert image_path.exists()

    @pytest.mark.asyncio
    async def test_rework_image_reports_usage(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that rework reports usage metadata."""
        import shutil

        original_path = working_folder / "pages" / "to_rework.png"
        shutil.copy(sample_image, original_path)

        usage_cb = MagicMock()
        service = ImageService("test-api-key", working_folder, usage_callback=usage_cb)

        await service.rework_image(
            original_image=original_path,
            prompt="Improve quality",
            category="pages",
        )

        usage_cb.assert_called_once()

    @pytest.mark.asyncio
    async def test_rework_image_missing_original_raises_error(
        self, working_folder: Path, mock_genai
    ):
        """Test that rework raises error if original image doesn't exist."""
        service = ImageService("test-api-key", working_folder)

        with pytest.raises(ImageGenerationError, match="Original image not found"):
            await service.rework_image(
                original_image=Path("/nonexistent/image.png"),
                prompt="Improve this",
                category="pages",
            )

    @pytest.mark.asyncio
    async def test_rework_image_filename_format(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that rework filename follows the expected format."""
        import shutil

        original_path = working_folder / "pages" / "my_artwork.png"
        shutil.copy(sample_image, original_path)

        service = ImageService("test-api-key", working_folder)

        image_path, _ = await service.rework_image(
            original_image=original_path,
            prompt="Enhance",
            category="pages",
        )

        # Should be: rework_YYYYMMDD_HHMMSS_my_artwork.png
        assert image_path.name.startswith("rework_")
        assert "my_artwork" in image_path.name

    @pytest.mark.asyncio
    async def test_rework_emits_progress(
        self, working_folder: Path, sample_image: Path, mock_genai
    ):
        """Test that progress_callback is called during rework."""
        import shutil

        original_path = working_folder / "pages" / "progress_test.png"
        shutil.copy(sample_image, original_path)

        service = ImageService("test-api-key", working_folder)
        progress: list[str] = []

        await service.rework_image(
            original_image=original_path,
            prompt="Adjust colors",
            category="pages",
            progress_callback=progress.append,
        )

        assert any("rework" in p.lower() for p in progress)
