"""Unit tests for the Image Cropper component.

Tests for the image cropper Python wrapper and utility functions.
"""

import pytest
import base64
from pathlib import Path
from PIL import Image
import io

from src.components.image_cropper import (
    save_cropped_image,
    image_to_data_url,
)


@pytest.mark.unit
class TestImageCropperUtils:
    """Tests for image cropper utility functions."""

    def test_save_cropped_image_basic(self, tmp_path: Path):
        """Test saving a cropped image from data URL."""
        # Create a simple test image as base64
        img = Image.new('RGB', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        data_url = f"data:image/png;base64,{base64_data}"
        
        output_path = tmp_path / "cropped.png"
        result = save_cropped_image(data_url, output_path)
        
        assert result == output_path
        assert output_path.exists()
        
        # Verify it's a valid image
        with Image.open(output_path) as saved_img:
            assert saved_img.size == (100, 100)

    def test_save_cropped_image_creates_directory(self, tmp_path: Path):
        """Test that save_cropped_image creates parent directories."""
        img = Image.new('RGB', (50, 50), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        data_url = f"data:image/png;base64,{base64_data}"
        
        output_path = tmp_path / "nested" / "folder" / "image.png"
        result = save_cropped_image(data_url, output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_save_cropped_image_raw_base64(self, tmp_path: Path):
        """Test saving with raw base64 data (no data URL prefix)."""
        img = Image.new('RGB', (30, 30), color='green')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        raw_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        output_path = tmp_path / "raw_output.png"
        result = save_cropped_image(raw_base64, output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_image_to_data_url_png(self, sample_image: Path):
        """Test converting a PNG image to data URL."""
        data_url = image_to_data_url(sample_image)
        
        assert data_url.startswith("data:image/png;base64,")
        
        # Verify we can decode it back
        _, base64_data = data_url.split(',', 1)
        image_bytes = base64.b64decode(base64_data)
        
        img = Image.open(io.BytesIO(image_bytes))
        assert img.size == (100, 100)

    def test_image_to_data_url_jpeg(self, tmp_path: Path):
        """Test converting a JPEG image to data URL."""
        # Create a JPEG test image
        img = Image.new('RGB', (80, 80), color='yellow')
        jpeg_path = tmp_path / "test.jpg"
        img.save(jpeg_path, format='JPEG')
        
        data_url = image_to_data_url(jpeg_path)
        
        assert data_url.startswith("data:image/jpeg;base64,")

    def test_image_to_data_url_roundtrip(self, tmp_path: Path):
        """Test that image survives encode/decode roundtrip."""
        # Create original image
        original = Image.new('RGB', (64, 64), color='purple')
        original_path = tmp_path / "original.png"
        original.save(original_path, format='PNG')
        
        # Convert to data URL
        data_url = image_to_data_url(original_path)
        
        # Save back from data URL
        roundtrip_path = tmp_path / "roundtrip.png"
        save_cropped_image(data_url, roundtrip_path)
        
        # Compare
        with Image.open(roundtrip_path) as roundtrip:
            assert roundtrip.size == (64, 64)
            # Check a pixel to verify color
            pixel = roundtrip.getpixel((32, 32))
            # Purple is approximately (128, 0, 128)
            assert pixel[0] > 100  # R
            assert pixel[1] < 50   # G
            assert pixel[2] > 100  # B


@pytest.mark.unit
class TestImageCropperDataValidation:
    """Tests for data validation in image cropper utilities."""

    def test_save_cropped_image_invalid_base64(self, tmp_path: Path):
        """Test that invalid base64 raises appropriate error."""
        output_path = tmp_path / "invalid.png"
        
        with pytest.raises(Exception):  # Could be ValueError or binascii.Error
            save_cropped_image("not-valid-base64!!!", output_path)

    def test_save_cropped_image_empty_data(self, tmp_path: Path):
        """Test handling of empty data - saves empty file."""
        output_path = tmp_path / "empty.png"
        
        # Empty base64 decodes to empty bytes, saves an empty file
        result = save_cropped_image("", output_path)
        assert result == output_path
        assert output_path.exists()
        assert output_path.stat().st_size == 0  # Empty file

    def test_image_to_data_url_nonexistent_file(self, tmp_path: Path):
        """Test handling of nonexistent file."""
        nonexistent = tmp_path / "does_not_exist.png"
        
        with pytest.raises(FileNotFoundError):
            image_to_data_url(nonexistent)


@pytest.mark.unit
class TestSaveCroppedImageDictHandling:
    """Tests for handling dict input to save_cropped_image (NiceGUI event args)."""

    def _create_test_data_url(self) -> str:
        """Create a valid test data URL."""
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{base64_data}"

    def test_save_cropped_image_browser_custom_event(self, tmp_path: Path):
        """Test handling browser CustomEvent structure with 'detail' key (NiceGUI event args)."""
        data_url = self._create_test_data_url()
        # This is the actual structure from browser CustomEvent objects
        browser_event = {
            'isTrusted': True,
            '_vts': 1734216153000,
            'detail': data_url,
            'type': 'crop',
            'eventPhase': 0,
            'bubbles': False,
            'cancelable': False,
            'defaultPrevented': False,
            'composed': False,
            'timeStamp': 12345.0,
            'returnValue': True,
            'cancelBubble': False,
            'NONE': 0,
            'CAPTURING_PHASE': 1,
            'AT_TARGET': 2,
            'BUBBLING_PHASE': 3,
        }
        
        output_path = tmp_path / "from_browser_event.png"
        result = save_cropped_image(browser_event, output_path)
        
        assert result == output_path
        assert output_path.exists()
        
        with Image.open(output_path) as saved_img:
            assert saved_img.size == (50, 50)

    def test_save_cropped_image_browser_custom_event_detail_list(self, tmp_path: Path):
        """Test handling CustomEvent where 'detail' is a list of emitted args (NiceGUI bridge)."""
        data_url = self._create_test_data_url()
        browser_event = {
            'isTrusted': True,
            '_vts': 1734216153000,
            'detail': [data_url],
            'type': 'crop',
        }

        output_path = tmp_path / "from_browser_event_detail_list.png"
        result = save_cropped_image(browser_event, output_path)

        assert result == output_path
        assert output_path.exists()

    def test_save_cropped_image_dict_with_dataUrl_key(self, tmp_path: Path):
        """Test handling dict with 'dataUrl' key (regression test for NiceGUI event args)."""
        data_url = self._create_test_data_url()
        dict_input = {'dataUrl': data_url}
        
        output_path = tmp_path / "from_dict.png"
        result = save_cropped_image(dict_input, output_path)
        
        assert result == output_path
        assert output_path.exists()
        
        with Image.open(output_path) as saved_img:
            assert saved_img.size == (50, 50)

    def test_save_cropped_image_dict_with_data_url_key(self, tmp_path: Path):
        """Test handling dict with 'data_url' key."""
        data_url = self._create_test_data_url()
        dict_input = {'data_url': data_url}
        
        output_path = tmp_path / "from_dict2.png"
        result = save_cropped_image(dict_input, output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_save_cropped_image_dict_with_data_key(self, tmp_path: Path):
        """Test handling dict with 'data' key."""
        data_url = self._create_test_data_url()
        dict_input = {'data': data_url}
        
        output_path = tmp_path / "from_dict3.png"
        result = save_cropped_image(dict_input, output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_save_cropped_image_dict_with_url_key(self, tmp_path: Path):
        """Test handling dict with 'url' key."""
        data_url = self._create_test_data_url()
        dict_input = {'url': data_url}
        
        output_path = tmp_path / "from_dict4.png"
        result = save_cropped_image(dict_input, output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_save_cropped_image_dict_fallback_to_string_value(self, tmp_path: Path):
        """Test handling dict with unknown key but string value starting with data:."""
        data_url = self._create_test_data_url()
        dict_input = {'unknownKey': data_url}
        
        output_path = tmp_path / "from_dict5.png"
        result = save_cropped_image(dict_input, output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_save_cropped_image_dict_without_valid_data_raises_error(self, tmp_path: Path):
        """Test that dict without valid data URL raises TypeError."""
        dict_input = {'notAnImage': 'short'}
        
        output_path = tmp_path / "should_fail.png"
        
        with pytest.raises(TypeError) as exc_info:
            save_cropped_image(dict_input, output_path)
        
        assert "Expected data_url to be a string or dict containing a data URL" in str(exc_info.value)

    def test_save_cropped_image_invalid_type_raises_error(self, tmp_path: Path):
        """Test that invalid type (not string or dict) raises TypeError."""
        output_path = tmp_path / "should_fail.png"
        
        with pytest.raises(TypeError) as exc_info:
            save_cropped_image(12345, output_path)  # type: ignore
        
        assert "Expected data_url to be a string" in str(exc_info.value)

    def test_save_cropped_image_list_raises_error(self, tmp_path: Path):
        """Test that list input raises TypeError."""
        data_url = self._create_test_data_url()
        output_path = tmp_path / "should_fail.png"
        
        with pytest.raises(TypeError) as exc_info:
            save_cropped_image([data_url], output_path)  # type: ignore
        
        assert "Expected data_url to be a string" in str(exc_info.value)
