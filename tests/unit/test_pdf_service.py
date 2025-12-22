"""Unit tests for the PDF Service."""

import pytest
from pathlib import Path
from PIL import Image

from src.services.pdf_service import PdfService, PdfExportError, ASPECT_RATIO_SIZES


@pytest.mark.unit
class TestPdfService:
    """Tests for the PdfService class."""

    def test_init(self):
        """Test PdfService initialization."""
        service = PdfService()
        assert service is not None

    def test_get_page_size_predefined(self):
        """Test getting predefined page sizes."""
        service = PdfService()

        for ratio, expected_size in ASPECT_RATIO_SIZES.items():
            result = service._get_page_size(ratio)
            assert result == expected_size

    def test_get_page_size_custom(self):
        """Test getting custom aspect ratio page sizes."""
        service = PdfService()

        # Custom ratio should still work
        result = service._get_page_size("2:3")
        assert result is not None
        assert len(result) == 2

    def test_get_page_size_invalid_fallback(self):
        """Test that invalid aspect ratio falls back to default."""
        service = PdfService()

        result = service._get_page_size("invalid")
        assert result == ASPECT_RATIO_SIZES["3:4"]

    def test_get_image_dimensions(self, sample_image: Path):
        """Test getting image dimensions."""
        service = PdfService()

        width, height = service._get_image_dimensions(sample_image)

        assert width == 100
        assert height == 100

    def test_create_pdf_single_page(self, working_folder: Path, sample_image: Path):
        """Test creating PDF with single page."""
        service = PdfService()
        output_path = working_folder / "test_single.pdf"

        result = service.create_pdf(
            page_images=[sample_image],
            output_path=output_path,
            aspect_ratio="3:4",
            title="Test Book",
        )

        assert result == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_create_pdf_multiple_pages(
        self, working_folder: Path, sample_images: list[Path]
    ):
        """Test creating PDF with multiple pages."""
        service = PdfService()
        output_path = working_folder / "test_multi.pdf"

        # Use page images
        pages = [img for img in sample_images if "page" in img.name]

        result = service.create_pdf(
            page_images=pages,
            output_path=output_path,
            aspect_ratio="3:4",
            title="Multi-page Book",
        )

        assert result == output_path
        assert output_path.exists()

    def test_create_pdf_empty_raises(self, working_folder: Path):
        """Test that creating PDF with no pages raises error."""
        service = PdfService()
        output_path = working_folder / "test_empty.pdf"

        with pytest.raises(PdfExportError, match="No pages to export"):
            service.create_pdf(page_images=[], output_path=output_path)

    def test_create_pdf_skips_missing_images(
        self, working_folder: Path, sample_image: Path
    ):
        """Test that missing images are skipped."""
        service = PdfService()
        output_path = working_folder / "test_skip.pdf"

        pages = [
            sample_image,
            Path("/nonexistent/image.png"),  # This will be skipped
        ]

        result = service.create_pdf(page_images=pages, output_path=output_path)

        assert result == output_path
        assert output_path.exists()

    def test_create_pdf_creates_output_directory(
        self, temp_dir: Path, sample_image: Path
    ):
        """Test that output directory is created if it doesn't exist."""
        service = PdfService()
        output_path = temp_dir / "nested" / "dirs" / "test.pdf"

        assert not output_path.parent.exists()

        service.create_pdf(page_images=[sample_image], output_path=output_path)

        assert output_path.exists()

    def test_create_pdf_different_aspect_ratios(
        self, working_folder: Path, sample_image: Path
    ):
        """Test creating PDFs with different aspect ratios."""
        service = PdfService()

        for ratio in ["1:1", "3:4", "4:3", "16:9", "9:16"]:
            output_path = (
                working_folder / "exports" / f"test_{ratio.replace(':', '_')}.pdf"
            )

            service.create_pdf(
                page_images=[sample_image], output_path=output_path, aspect_ratio=ratio
            )

            assert output_path.exists()

    def test_create_pdf_with_cover(
        self, working_folder: Path, sample_images: list[Path]
    ):
        """Test creating PDF with cover page."""
        service = PdfService()
        output_path = working_folder / "exports" / "test_cover.pdf"

        pages = [img for img in sample_images if "page" in img.name]
        cover = next(img for img in sample_images if "char" in img.name)

        result = service.create_pdf_with_cover(
            cover_image=cover,
            page_images=pages,
            output_path=output_path,
            title="Book with Cover",
        )

        assert result == output_path
        assert output_path.exists()

    def test_create_pdf_with_cover_none(
        self, working_folder: Path, sample_images: list[Path]
    ):
        """Test creating PDF without cover page."""
        service = PdfService()
        output_path = working_folder / "exports" / "test_no_cover.pdf"

        pages = [img for img in sample_images if "page" in img.name]

        result = service.create_pdf_with_cover(
            cover_image=None, page_images=pages, output_path=output_path
        )

        assert result == output_path
        assert output_path.exists()

    def test_create_pdf_with_cover_missing_cover(
        self, working_folder: Path, sample_images: list[Path]
    ):
        """Test creating PDF with non-existent cover."""
        service = PdfService()
        output_path = working_folder / "exports" / "test_missing_cover.pdf"

        pages = [img for img in sample_images if "page" in img.name]

        result = service.create_pdf_with_cover(
            cover_image=Path("/nonexistent/cover.png"),
            page_images=pages,
            output_path=output_path,
        )

        assert result == output_path
        assert output_path.exists()

    def test_estimate_file_size(self, sample_images: list[Path]):
        """Test file size estimation."""
        service = PdfService()

        pages = [img for img in sample_images if "page" in img.name]

        estimate = service.estimate_file_size(pages)

        assert estimate > 0
        assert isinstance(estimate, int)

    def test_estimate_file_size_empty(self):
        """Test file size estimation with no pages."""
        service = PdfService()

        estimate = service.estimate_file_size([])

        # Should return just the overhead
        assert estimate == 10000

    def test_estimate_file_size_missing_files(self, sample_image: Path):
        """Test file size estimation with missing files."""
        service = PdfService()

        estimate = service.estimate_file_size(
            [
                sample_image,
                Path("/nonexistent/image.png"),
            ]
        )

        # Should only count existing files
        assert estimate > 10000  # Overhead + one image


@pytest.mark.unit
class TestPdfServiceImageHandling:
    """Tests for image handling in PDF creation."""

    def test_pdf_preserves_image_quality(self, working_folder: Path, temp_dir: Path):
        """Test that images are properly embedded in PDF."""
        service = PdfService()

        # Create a test image with specific dimensions
        test_image = temp_dir / "quality_test.png"
        img = Image.new("RGB", (800, 600), color="blue")
        img.save(test_image)

        output_path = working_folder / "exports" / "quality_test.pdf"

        service.create_pdf(page_images=[test_image], output_path=output_path)

        assert output_path.exists()
        # PDF should be larger than 0 (contains image data)
        assert output_path.stat().st_size > 1000

    def test_pdf_handles_rgba_images(self, working_folder: Path, temp_dir: Path):
        """Test that RGBA images are handled correctly."""
        service = PdfService()

        # Create RGBA image
        test_image = temp_dir / "rgba_test.png"
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        img.save(test_image)

        output_path = working_folder / "exports" / "rgba_test.pdf"

        # Should not raise
        service.create_pdf(page_images=[test_image], output_path=output_path)

        assert output_path.exists()

    def test_pdf_handles_different_image_formats(
        self, working_folder: Path, temp_dir: Path
    ):
        """Test that different image formats are handled."""
        service = PdfService()

        images = []
        for fmt, ext in [("PNG", ".png"), ("JPEG", ".jpg")]:
            img_path = temp_dir / f"test{ext}"
            img = Image.new("RGB", (100, 100), color="green")
            img.save(img_path, fmt)
            images.append(img_path)

        output_path = working_folder / "exports" / "formats_test.pdf"

        service.create_pdf(page_images=images, output_path=output_path)

        assert output_path.exists()
