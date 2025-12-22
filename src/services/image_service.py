"""Image generation service for Book Creator.

Wraps the Gemini API for image generation with support for:
- Text-to-image generation
- Image-to-image with reference images
- Sketch-based generation
- Automatic thumbnail creation
- Single request at a time (asyncio lock)
"""

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Callable

from PIL import Image
from google import genai
from google.genai import types

from src.services.gemini_usage import GeminiUsage, extract_gemini_usage
from src.services.ai_config import (
    load_ai_config,
    get_model,
    get_system_prompts,
    get_templates,
)

logger = logging.getLogger(__name__)

# Constants
THUMBNAIL_SIZE = 256
MAX_PROMPT_CHARS = 8000
MAX_REFERENCE_IMAGES = 16

_AI_CONFIG = load_ai_config()

# Model names are configured in ai_config.json
IMAGE_MODEL = get_model(
    "image_generation", config=_AI_CONFIG
)  # Model that supports image generation

# System prompts are configured in ai_config.json
SYSTEM_PROMPTS = get_system_prompts(config=_AI_CONFIG)
TEMPLATES = get_templates(config=_AI_CONFIG)


class ImageGenerationError(Exception):
    """Raised when image generation fails."""

    def __init__(self, message: str, is_api_error: bool = False):
        super().__init__(message)
        self.is_api_error = is_api_error


class ImageService:
    """Service for generating images using Google's Gemini API."""

    def __init__(
        self,
        api_key: str,
        working_folder: Path,
        usage_callback: Optional[Callable[[GeminiUsage], None]] = None,
        system_prompt_overrides: Optional[dict[str, str]] = None,
    ):
        """Initialize the image service.

        Args:
            api_key: Gemini API key.
            working_folder: Base folder for storing generated images.
            usage_callback: Optional callback for usage tracking.
            system_prompt_overrides: Optional dict of system prompt key -> override text.
        """
        self._client = genai.Client(api_key=api_key)
        self._working_folder = working_folder
        self._lock = asyncio.Lock()
        self._is_generating = False
        self._usage_callback = usage_callback
        self._system_prompt_overrides = system_prompt_overrides or {}

    def set_system_prompt_overrides(self, overrides: dict[str, str]) -> None:
        """Update system prompt overrides.

        Args:
            overrides: Dict of system prompt key -> override text.
        """
        self._system_prompt_overrides = overrides or {}

    def get_system_prompt(self, key: str) -> str:
        """Get a system prompt, checking overrides first.

        Args:
            key: System prompt key (e.g., "character_sheet", "page").

        Returns:
            The override if set, otherwise the default from ai_config.json.
        """
        if key in self._system_prompt_overrides and self._system_prompt_overrides[key]:
            return self._system_prompt_overrides[key]
        return SYSTEM_PROMPTS.get(key, "")

    @property
    def is_generating(self) -> bool:
        """Check if a generation is currently in progress."""
        return self._is_generating

    def _validate_prompt(self, prompt: str) -> str:
        cleaned = (prompt or "").strip()
        if not cleaned:
            raise ImageGenerationError("Prompt is empty")
        if len(cleaned) > MAX_PROMPT_CHARS:
            raise ImageGenerationError(
                f"Prompt is too long (max {MAX_PROMPT_CHARS} characters)"
            )
        return cleaned

    def _validate_attachments(
        self,
        reference_images: Optional[list[Path]],
        sketch: Optional[Path],
    ) -> tuple[Optional[list[Path]], Optional[Path]]:
        refs: Optional[list[Path]] = None
        if reference_images:
            # Keep only existing files and cap the count to avoid huge payloads.
            existing = [
                p
                for p in reference_images
                if isinstance(p, Path) and p.exists() and p.is_file()
            ]
            if len(existing) > MAX_REFERENCE_IMAGES:
                raise ImageGenerationError(
                    f"Too many reference images (max {MAX_REFERENCE_IMAGES})"
                )
            refs = existing or None

        sketch_path: Optional[Path] = None
        if sketch is not None:
            if not isinstance(sketch, Path):
                raise ImageGenerationError("Invalid sketch path")
            if sketch.exists() and sketch.is_file():
                sketch_path = sketch
            elif sketch.exists():
                raise ImageGenerationError("Sketch path is not a file")
            else:
                # Missing sketch is treated as "no sketch".
                sketch_path = None

        return refs, sketch_path

    def _get_mime_type(self, path: Path) -> str:
        """Determine MIME type for an image file."""
        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "image/jpeg"

    def _load_image_as_part(self, image_path: Path) -> types.Part:
        """Load an image file and convert to Gemini Part.

        Args:
            image_path: Path to the image file.

        Returns:
            Gemini Part object containing the image data.
        """
        mime_type = self._get_mime_type(image_path)
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    def _create_thumbnail(self, image_path: Path) -> Path:
        """Create a thumbnail for the given image.

        Args:
            image_path: Path to the source image.

        Returns:
            Path to the created thumbnail.
        """
        thumbnails_folder = self._working_folder / ".thumbnails"
        thumbnails_folder.mkdir(parents=True, exist_ok=True)

        thumbnail_path = thumbnails_folder / f"{image_path.stem}_thumb.png"

        with Image.open(image_path) as img:
            # Convert to RGB if necessary (handles RGBA, P mode, etc.)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Calculate thumbnail size maintaining aspect ratio
            img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
            img.save(thumbnail_path, "PNG")

        logger.info(f"Created thumbnail: {thumbnail_path}")
        return thumbnail_path

    def _save_generated_image(
        self, data: bytes, mime_type: str, category: str, name_prefix: str = "generated"
    ) -> Path:
        """Save generated image data to file.

        Args:
            data: Image binary data.
            mime_type: MIME type of the image.
            category: Category folder (pages, characters, etc.).
            name_prefix: Prefix for the filename.

        Returns:
            Path to the saved image.
        """
        from datetime import datetime

        # Determine file extension
        extension = mimetypes.guess_extension(mime_type) or ".png"

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"{name_prefix}_{timestamp}{extension}"

        # Save to category folder
        category_folder = self._working_folder / category
        category_folder.mkdir(parents=True, exist_ok=True)
        output_path = category_folder / filename

        with open(output_path, "wb") as f:
            f.write(data)

        logger.info(f"Saved generated image: {output_path}")
        return output_path

    def _build_prompt(
        self,
        user_prompt: str,
        style_prompt: str = "",
        system_prompt_key: Optional[str] = None,
    ) -> str:
        """Build the full prompt from components.

        Args:
            user_prompt: The user's specific prompt.
            style_prompt: Overarching style description (deprecated, now in system prompt).
            system_prompt_key: Key for baked-in system prompt.

        Returns:
            Combined prompt string.
        """
        parts = []

        # System prompts are provided via GenerateContentConfig.system_instruction.
        # Style prompts are now also part of the system instruction.
        # This function only builds the user-visible prompt content.

        # Add user prompt
        parts.append(user_prompt)

        return "\n\n".join(parts)

    async def generate_image(
        self,
        prompt: str,
        reference_images: Optional[list[Path]] = None,
        sketch: Optional[Path] = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        image_size: str = "4K",
        category: str = "pages",
        system_prompt_key: Optional[str] = None,
        p_threshold: float = 0.95,
        temperature: float = 1.0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Path, Path]:
        """Generate an image using the Gemini API.

        Args:
            prompt: The generation prompt.
            reference_images: Optional list of reference image paths.
            sketch: Optional sketch image path.
            style_prompt: Overarching style description.
            aspect_ratio: Output aspect ratio (e.g., "3:4").
            image_size: Output resolution (e.g., "4K").
            category: Output category folder.
            system_prompt_key: Key for baked-in system prompt.
            p_threshold: Nucleus sampling probability (0.0 to 1.0).
            temperature: Sampling temperature (0.0 to 2.0).

        Returns:
            Tuple of (full_image_path, thumbnail_path).

        Raises:
            ImageGenerationError: If generation fails.
        """
        prompt = self._validate_prompt(prompt)
        reference_images, sketch = self._validate_attachments(reference_images, sketch)

        async with self._lock:
            self._is_generating = True
            try:
                return await self._generate_image_impl(
                    prompt=prompt,
                    reference_images=reference_images,
                    sketch=sketch,
                    style_prompt=style_prompt,
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                    category=category,
                    system_prompt_key=system_prompt_key,
                    p_threshold=p_threshold,
                    temperature=temperature,
                    progress_callback=progress_callback,
                )
            finally:
                self._is_generating = False

    async def _generate_image_impl(
        self,
        prompt: str,
        reference_images: Optional[list[Path]] = None,
        sketch: Optional[Path] = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        image_size: str = "4K",
        category: str = "pages",
        system_prompt_key: Optional[str] = None,
        p_threshold: float = 0.95,
        temperature: float = 1.0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Path, Path]:
        """Internal implementation of image generation."""
        # Build the user prompt (system instruction handled separately)
        full_prompt = self._build_prompt(prompt, style_prompt, system_prompt_key)

        system_instruction = ""
        if system_prompt_key:
            system_instruction = self.get_system_prompt(system_prompt_key)

        # Add style prompt to system instruction
        if style_prompt:
            style_prefix = TEMPLATES.get("style_prefix", "Style: {style_prompt}")
            formatted_style = style_prefix.format(style_prompt=style_prompt)
            if system_instruction:
                system_instruction += "\n\n" + formatted_style
            else:
                system_instruction = formatted_style

        system_instruction = (system_instruction or "").strip()

        # Log the model and prompt details
        logger.info("=" * 60)
        logger.info(f"MODEL: {IMAGE_MODEL}")
        logger.info(f"ASPECT RATIO: {aspect_ratio}")
        logger.info(f"CATEGORY: {category}")
        logger.info(f"Top-P: {p_threshold}, TEMPERATURE: {temperature}")
        logger.info("-" * 60)
        logger.info("PROMPT:")
        logger.info(full_prompt)
        if system_instruction:
            logger.info("-" * 60)
            logger.info("SYSTEM INSTRUCTION:")
            logger.info(system_instruction)
        logger.info("-" * 60)

        # Build content parts
        parts = [types.Part.from_text(text=full_prompt)]

        # Log and add reference images
        attached_images = []
        if reference_images:
            logger.info(f"REFERENCE IMAGES ({len(reference_images)} total):")
            for image_path in reference_images:
                if image_path.exists():
                    parts.append(self._load_image_as_part(image_path))
                    attached_images.append(str(image_path))
                    logger.info(f"  ✓ {image_path}")
                else:
                    logger.warning(f"  ✗ Reference image not found: {image_path}")
        else:
            logger.info("REFERENCE IMAGES: None")

        # Add sketch if provided
        if sketch and sketch.exists():
            parts.append(self._load_image_as_part(sketch))
            attached_images.append(str(sketch))
            logger.info(f"SKETCH: {sketch}")
        else:
            logger.info("SKETCH: None")

        logger.info("-" * 60)
        logger.info(f"TOTAL IMAGES ATTACHED: {len(attached_images)}")
        logger.info("=" * 60)

        # Create content
        contents = [
            types.Content(role="user", parts=parts),
        ]

        # Configure generation
        config = types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
            top_p=p_threshold,
            temperature=temperature,
        )

        # Run generation in executor to not block event loop
        if progress_callback:
            progress_callback("Waiting for Gemini to finish image generation...")
        loop = asyncio.get_event_loop()
        api_result = await loop.run_in_executor(
            None, lambda: self._call_api(contents, config)
        )

        if api_result is None:
            raise ImageGenerationError("No image was generated")

        image_bytes, mime_type = api_result

        if progress_callback:
            progress_callback("Saving generated image...")
        image_path = self._save_generated_image(
            data=image_bytes,
            mime_type=mime_type,
            category=category,
        )

        if progress_callback:
            progress_callback("Creating thumbnail...")
        thumbnail_path = self._create_thumbnail(image_path)

        return (image_path, thumbnail_path)

    def _call_api(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> Optional[tuple[bytes, str]]:
        """Synchronous API call (run in executor).

        Returns:
            Tuple of (image_bytes, mime_type) or None if no image generated.
        """
        try:
            logger.info(f"Calling Gemini API with model: {IMAGE_MODEL}...")

            image_bytes: Optional[bytes] = None
            mime_type: Optional[str] = None
            usage: Optional[GeminiUsage] = None

            for chunk in self._client.models.generate_content_stream(
                model=IMAGE_MODEL,
                contents=contents,
                config=config,
            ):
                extracted = extract_gemini_usage(chunk, model=IMAGE_MODEL)
                if (
                    extracted.prompt_tokens is not None
                    or extracted.output_tokens is not None
                    or extracted.total_tokens is not None
                    or extracted.cost is not None
                ):
                    usage = extracted

                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue

                # A single chunk can contain multiple parts; don't assume index 0.
                for part in chunk.candidates[0].content.parts:
                    if part is None:
                        continue
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        image_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type
                    elif getattr(part, "text", None):
                        # Log any text response (often contains explanation or error)
                        if part.text:
                            logger.info(f"API text response: {part.text}")

                if (
                    image_bytes is not None
                    and mime_type is not None
                    and usage is not None
                    and usage.total_tokens is not None
                ):
                    break

            if self._usage_callback is not None and usage is not None:
                try:
                    self._usage_callback(usage)
                except Exception as e:  # pragma: no cover
                    logger.debug(f"Usage callback failed: {e}")

            if image_bytes is None or mime_type is None:
                return None
            return (image_bytes, mime_type)

        except Exception as e:
            logger.exception(f"API call failed: {e}")
            raise ImageGenerationError(
                f"Gemini API Error: {e}", is_api_error=True
            ) from e

    async def generate_character_sheet(
        self,
        description: str,
        reference_photos: Optional[list[Path]] = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        image_size: str = "4K",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Path, Path]:
        """Generate a character reference sheet.

        Args:
            description: Description of the character.
            reference_photos: Optional reference photos.
            style_prompt: Overarching style description.
            aspect_ratio: Output aspect ratio.
            image_size: Output resolution.

        Returns:
            Tuple of (image_path, thumbnail_path).
        """
        return await self.generate_image(
            prompt=description,
            reference_images=reference_photos,
            style_prompt=style_prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            category="references",
            system_prompt_key="character_sheet",
            progress_callback=progress_callback,
        )

    async def generate_page(
        self,
        scene_description: str,
        character_sheets: Optional[list[Path]] = None,
        sketch: Optional[Path] = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        image_size: str = "4K",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Path, Path]:
        """Generate a book page illustration.

        Args:
            scene_description: Description of the scene.
            character_sheets: Optional character reference images.
            sketch: Optional sketch for composition.
            style_prompt: Overarching style description.
            aspect_ratio: Output aspect ratio.
            image_size: Output resolution.

        Returns:
            Tuple of (image_path, thumbnail_path).
        """
        return await self.generate_image(
            prompt=scene_description,
            reference_images=character_sheets,
            sketch=sketch,
            style_prompt=style_prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            category="pages",
            system_prompt_key="page",
            progress_callback=progress_callback,
        )

    def get_thumbnail_path(self, image_path: Path) -> Optional[Path]:
        """Get the thumbnail path for an existing image.

        Args:
            image_path: Path to the full-size image.

        Returns:
            Path to the thumbnail, or None if it doesn't exist.
        """
        thumbnail_path = (
            self._working_folder / ".thumbnails" / f"{image_path.stem}_thumb.png"
        )
        return thumbnail_path if thumbnail_path.exists() else None

    def ensure_thumbnail(self, image_path: Path) -> Path:
        """Ensure a thumbnail exists for the image, creating if needed.

        Args:
            image_path: Path to the full-size image.

        Returns:
            Path to the thumbnail.
        """
        existing = self.get_thumbnail_path(image_path)
        if existing:
            return existing
        return self._create_thumbnail(image_path)

    async def rework_image(
        self,
        original_image: Path,
        prompt: str,
        additional_references: Optional[list[Path]] = None,
        sketch: Optional[Path] = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        image_size: str = "4K",
        category: str = "pages",
        p_threshold: float = 0.95,
        temperature: float = 1.0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Path, Path]:
        """Rework an existing image based on user instructions.

        The original image is sent as the first reference, and the new image
        is saved with a 'rework_' prefix, preserving the original.

        Args:
            original_image: Path to the original image to rework.
            prompt: User instructions for how to modify the image.
            additional_references: Optional additional reference images.
            sketch: Optional sketch for composition changes.
            style_prompt: Overarching style description.
            aspect_ratio: Output aspect ratio.
            image_size: Output resolution.
            category: Output category folder ('pages' or 'characters').
            p_threshold: Nucleus sampling probability (0.0 to 1.0).
            temperature: Sampling temperature (0.0 to 2.0).
            progress_callback: Optional progress callback.

        Returns:
            Tuple of (reworked_image_path, thumbnail_path).

        Raises:
            ImageGenerationError: If rework fails.
        """
        prompt = self._validate_prompt(prompt)

        if not original_image.exists():
            raise ImageGenerationError(f"Original image not found: {original_image}")

        # Build reference list with original image first
        reference_images = [original_image]
        if additional_references:
            reference_images.extend(additional_references)

        reference_images, sketch = self._validate_attachments(reference_images, sketch)

        # Determine system prompt based on category
        system_prompt_key = "rework_page" if category == "pages" else "rework_character"

        # Format the prompt using the rework template
        rework_template = TEMPLATES.get(
            "rework_instruction",
            "Original image is provided as the first reference. Requested changes: {prompt}",
        )
        full_user_prompt = rework_template.format(prompt=prompt)

        async with self._lock:
            self._is_generating = True
            try:
                return await self._rework_image_impl(
                    prompt=full_user_prompt,
                    original_image=original_image,
                    reference_images=reference_images,
                    sketch=sketch,
                    style_prompt=style_prompt,
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                    category=category,
                    system_prompt_key=system_prompt_key,
                    p_threshold=p_threshold,
                    temperature=temperature,
                    progress_callback=progress_callback,
                )
            finally:
                self._is_generating = False

    async def _rework_image_impl(
        self,
        prompt: str,
        original_image: Path,
        reference_images: Optional[list[Path]] = None,
        sketch: Optional[Path] = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        image_size: str = "4K",
        category: str = "pages",
        system_prompt_key: Optional[str] = None,
        p_threshold: float = 0.95,
        temperature: float = 1.0,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[Path, Path]:
        """Internal implementation of image rework."""
        # Build the user prompt
        full_prompt = self._build_prompt(prompt, style_prompt, system_prompt_key)

        system_instruction = ""
        if system_prompt_key:
            system_instruction = self.get_system_prompt(system_prompt_key)

        # Add style prompt to system instruction
        if style_prompt:
            style_prefix = TEMPLATES.get("style_prefix", "Style: {style_prompt}")
            formatted_style = style_prefix.format(style_prompt=style_prompt)
            if system_instruction:
                system_instruction += "\n\n" + formatted_style
            else:
                system_instruction = formatted_style

        system_instruction = (system_instruction or "").strip()

        # Log the model and prompt details
        logger.info("=" * 60)
        logger.info(f"REWORK IMAGE - MODEL: {IMAGE_MODEL}")
        logger.info(f"ORIGINAL: {original_image}")
        logger.info(f"ASPECT RATIO: {aspect_ratio}")
        logger.info(f"CATEGORY: {category}")
        logger.info(f"Top-P: {p_threshold}, TEMPERATURE: {temperature}")
        logger.info("-" * 60)
        logger.info("PROMPT:")
        logger.info(full_prompt)
        if system_instruction:
            logger.info("-" * 60)
            logger.info("SYSTEM INSTRUCTION:")
            logger.info(system_instruction)
        logger.info("-" * 60)

        # Build content parts
        parts = [types.Part.from_text(text=full_prompt)]

        # Log and add reference images (original first)
        attached_images = []
        if reference_images:
            logger.info(f"REFERENCE IMAGES ({len(reference_images)} total):")
            for image_path in reference_images:
                if image_path.exists():
                    parts.append(self._load_image_as_part(image_path))
                    attached_images.append(str(image_path))
                    marker = "[ORIGINAL]" if image_path == original_image else ""
                    logger.info(f"  ✓ {image_path} {marker}")
                else:
                    logger.warning(f"  ✗ Reference image not found: {image_path}")

        # Add sketch if provided
        if sketch and sketch.exists():
            parts.append(self._load_image_as_part(sketch))
            attached_images.append(str(sketch))
            logger.info(f"SKETCH: {sketch}")
        else:
            logger.info("SKETCH: None")

        logger.info("-" * 60)
        logger.info(f"TOTAL IMAGES ATTACHED: {len(attached_images)}")
        logger.info("=" * 60)

        # Create content
        contents = [
            types.Content(role="user", parts=parts),
        ]

        # Configure generation
        config = types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
            top_p=p_threshold,
            temperature=temperature,
        )

        # Run generation in executor to not block event loop
        if progress_callback:
            progress_callback("Waiting for Gemini to finish image generation...")
        loop = asyncio.get_event_loop()
        api_result = await loop.run_in_executor(
            None, lambda: self._call_api(contents, config)
        )

        if api_result is None:
            raise ImageGenerationError("No image was generated during rework")

        image_bytes, mime_type = api_result

        if progress_callback:
            progress_callback("Saving reworked image...")

        # Save with rework prefix
        image_path = self._save_reworked_image(
            data=image_bytes,
            mime_type=mime_type,
            category=category,
            original_name=original_image.stem,
        )

        if progress_callback:
            progress_callback("Creating thumbnail...")
        thumbnail_path = self._create_thumbnail(image_path)

        return (image_path, thumbnail_path)

    def _save_reworked_image(
        self,
        data: bytes,
        mime_type: str,
        category: str,
        original_name: str,
    ) -> Path:
        """Save reworked image with timestamp prefix preserving original name reference.

        Args:
            data: Image binary data.
            mime_type: MIME type of the image.
            category: Category folder (pages, characters, etc.).
            original_name: Original image filename stem for reference.

        Returns:
            Path to the saved image.
        """
        from datetime import datetime

        # Determine file extension
        extension = mimetypes.guess_extension(mime_type) or ".png"

        # Generate filename with rework prefix and timestamp
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"rework_{timestamp}_{original_name}{extension}"

        # Save to category folder
        category_folder = self._working_folder / category
        category_folder.mkdir(parents=True, exist_ok=True)
        output_path = category_folder / filename

        with open(output_path, "wb") as f:
            f.write(data)

        logger.info(f"Saved reworked image: {output_path}")
        return output_path
