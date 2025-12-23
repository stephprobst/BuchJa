"""PDF Export Service for BuchJa.

Uses ReportLab (BSD license) to compile book pages into a PDF document.
"""

import logging
from pathlib import Path
from typing import Optional

from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from PIL import Image

logger = logging.getLogger(__name__)

# Aspect ratio to page size mapping
ASPECT_RATIO_SIZES = {
    "1:1": (8 * inch, 8 * inch),
    "3:4": (6 * inch, 8 * inch),
    "4:3": (8 * inch, 6 * inch),
    "16:9": (10 * inch, 5.625 * inch),
    "9:16": (5.625 * inch, 10 * inch),
}


class PdfExportError(Exception):
    """Raised when PDF export fails."""

    pass


class PdfService:
    """Service for exporting book pages to PDF."""

    def __init__(self):
        """Initialize the PDF service."""
        pass

    def _get_page_size(self, aspect_ratio: str) -> tuple[float, float]:
        """Get page dimensions for the given aspect ratio.

        Args:
            aspect_ratio: Aspect ratio string (e.g., "3:4").

        Returns:
            Tuple of (width, height) in points.
        """
        if aspect_ratio in ASPECT_RATIO_SIZES:
            return ASPECT_RATIO_SIZES[aspect_ratio]

        # Parse custom aspect ratio
        try:
            w, h = aspect_ratio.split(":")
            ratio = float(w) / float(h)

            # Base on A4 size
            if ratio >= 1:
                # Landscape-ish
                return (8 * inch, 8 * inch / ratio)
            else:
                # Portrait-ish
                return (8 * inch * ratio, 8 * inch)
        except (ValueError, ZeroDivisionError):
            logger.warning(f"Invalid aspect ratio: {aspect_ratio}, using 3:4")
            return ASPECT_RATIO_SIZES["3:4"]

    def _get_image_dimensions(self, image_path: Path) -> tuple[int, int]:
        """Get the dimensions of an image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Tuple of (width, height) in pixels.
        """
        with Image.open(image_path) as img:
            return img.size

    def create_pdf(
        self,
        page_images: list[Path],
        output_path: Path,
        aspect_ratio: str = "3:4",
        title: str = "My Book",
        author: str = "BuchJa",
    ) -> Path:
        """Create a PDF from a list of page images.

        Args:
            page_images: List of paths to page images in order.
            output_path: Path where to save the PDF.
            aspect_ratio: Aspect ratio for page sizing.
            title: PDF document title.
            author: PDF document author.

        Returns:
            Path to the created PDF file.

        Raises:
            PdfExportError: If export fails.
        """
        if not page_images:
            raise PdfExportError("No pages to export")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get page size
        page_width, page_height = self._get_page_size(aspect_ratio)

        try:
            # Create PDF canvas
            c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

            # Set document metadata
            c.setTitle(title)
            c.setAuthor(author)
            c.setCreator("BuchJa")

            # Add each page
            for i, image_path in enumerate(page_images):
                if not image_path.exists():
                    logger.warning(f"Page image not found, skipping: {image_path}")
                    continue

                # Get image dimensions
                img_width, img_height = self._get_image_dimensions(image_path)

                # Calculate scaling to fit page while maintaining aspect ratio
                scale_x = page_width / img_width
                scale_y = page_height / img_height
                scale = min(scale_x, scale_y)

                # Calculate position to center image
                scaled_width = img_width * scale
                scaled_height = img_height * scale
                x = (page_width - scaled_width) / 2
                y = (page_height - scaled_height) / 2

                # Draw image
                c.drawImage(
                    str(image_path),
                    x,
                    y,
                    width=scaled_width,
                    height=scaled_height,
                    preserveAspectRatio=True,
                )

                # Add new page (except for last image)
                if i < len(page_images) - 1:
                    c.showPage()

                logger.info(f"Added page {i + 1}: {image_path.name}")

            # Save PDF
            c.save()

            logger.info(f"PDF exported to: {output_path}")
            return output_path

        except Exception as e:
            logger.exception(f"PDF export failed: {e}")
            raise PdfExportError(f"Failed to create PDF: {e}") from e

    def create_pdf_with_cover(
        self,
        cover_image: Optional[Path],
        page_images: list[Path],
        output_path: Path,
        aspect_ratio: str = "3:4",
        title: str = "My Book",
        author: str = "BuchJa",
    ) -> Path:
        """Create a PDF with a cover page.

        Args:
            cover_image: Optional path to cover image.
            page_images: List of paths to page images in order.
            output_path: Path where to save the PDF.
            aspect_ratio: Aspect ratio for page sizing.
            title: PDF document title.
            author: PDF document author.

        Returns:
            Path to the created PDF file.
        """
        all_pages = []
        if cover_image and cover_image.exists():
            all_pages.append(cover_image)
        all_pages.extend(page_images)

        return self.create_pdf(
            page_images=all_pages,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            title=title,
            author=author,
        )

    def estimate_file_size(self, page_images: list[Path]) -> int:
        """Estimate the resulting PDF file size.

        Args:
            page_images: List of page image paths.

        Returns:
            Estimated size in bytes.
        """
        total_size = 0
        for path in page_images:
            if path.exists():
                # Rough estimate: PDF overhead + compressed image
                # Images in PDF are typically 60-80% of original size
                total_size += int(path.stat().st_size * 0.7)

        # Add PDF overhead (metadata, structure)
        total_size += 10000  # ~10KB overhead

        return total_size
