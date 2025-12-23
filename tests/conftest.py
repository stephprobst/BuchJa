"""Pytest configuration and shared fixtures for BuchJa tests.

All tests mock external APIs (Gemini) to avoid token usage and costs.
"""

import json
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# Register pytest-nicegui User fixtures (provides 'user' fixture for UI testing)
# Note: Use 'user_plugin' instead of 'plugin' to avoid selenium dependency
pytest_plugins = ["nicegui.testing.user_plugin"]


# =============================================================================
# Fixtures: Temporary Directories
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def working_folder(temp_dir: Path) -> Path:
    """Create a working folder with proper structure."""
    working = temp_dir / "test_project"
    working.mkdir()

    # Create subdirectories
    for subdir in ["inputs", "references", "pages", ".thumbnails"]:
        (working / subdir).mkdir()

    return working


@pytest.fixture
def config_path(temp_dir: Path) -> Path:
    """Create a temporary config file path."""
    return temp_dir / "config.json"


# =============================================================================
# Fixtures: Sample Images
# =============================================================================


@pytest.fixture
def sample_image(temp_dir: Path) -> Path:
    """Create a sample test image."""
    image_path = temp_dir / "sample.png"

    # Create a simple test image
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)

    return image_path


@pytest.fixture
def sample_images(working_folder: Path) -> list[Path]:
    """Create multiple sample images in different categories."""
    images = []

    # Create character images (now in references)
    for i in range(2):
        path = working_folder / "references" / f"char_{i}.png"
        img = Image.new("RGB", (200, 300), color="blue")
        img.save(path)
        images.append(path)

    # Create page images
    for i in range(3):
        path = working_folder / "pages" / f"page_{i}.png"
        img = Image.new("RGB", (300, 400), color="green")
        img.save(path)
        images.append(path)

    # Create input images
    for i in range(2):
        path = working_folder / "inputs" / f"reference_{i}.jpg"
        img = Image.new("RGB", (150, 150), color="yellow")
        img.save(path, "JPEG")
        images.append(path)

    return images


# =============================================================================
# Fixtures: Mock Gemini API
# =============================================================================


@pytest.fixture
def mock_genai_response():
    """Create a mock Gemini API response with image data."""
    # Create a simple PNG image in memory
    img = Image.new("RGB", (100, 100), color="purple")
    import io

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    # Create mock response structure
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = image_bytes
    mock_part.inline_data.mime_type = "image/png"
    mock_part.text = None

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_chunk = MagicMock()
    mock_chunk.candidates = [mock_candidate]

    # Include usage metadata (Gemini SDK shape) so the app can track tokens.
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 10
    mock_usage.response_token_count = 20
    mock_usage.total_token_count = 30
    mock_chunk.usage_metadata = mock_usage

    return [mock_chunk]


@pytest.fixture
def mock_genai_client(mock_genai_response):
    """Create a mock Gemini API client."""
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = mock_genai_response

    return mock_client


@pytest.fixture
def mock_genai(mock_genai_client):
    """Patch the genai module to use mock client."""
    with patch("src.services.image_service.genai") as mock_genai_module:
        mock_genai_module.Client.return_value = mock_genai_client
        yield mock_genai_module


# =============================================================================
# Fixtures: Mock Keyring
# =============================================================================


@pytest.fixture
def mock_keyring():
    """Mock the keyring module to avoid system keystore access."""
    stored_passwords = {}

    def mock_get_password(service, username):
        return stored_passwords.get((service, username))

    def mock_set_password(service, username, password):
        stored_passwords[(service, username)] = password

    def mock_delete_password(service, username):
        key = (service, username)
        if key in stored_passwords:
            del stored_passwords[key]
        else:
            from keyring.errors import PasswordDeleteError

            raise PasswordDeleteError("Password not found")

    with patch("src.services.settings.keyring") as mock_kr:
        mock_kr.get_password = MagicMock(side_effect=mock_get_password)
        mock_kr.set_password = MagicMock(side_effect=mock_set_password)
        mock_kr.delete_password = MagicMock(side_effect=mock_delete_password)
        mock_kr.errors = MagicMock()
        mock_kr.errors.KeyringError = Exception
        mock_kr.errors.PasswordDeleteError = Exception
        yield mock_kr, stored_passwords


# =============================================================================
# Fixtures: Project Data
# =============================================================================


@pytest.fixture
def sample_project_data() -> dict:
    """Create sample project data structure."""
    return {
        "pages": [
            {
                "id": "page001",
                "path": "pages/page_0.png",
                "category": "pages",
                "name": "Page 1",
                "order": 1,
            },
            {
                "id": "page002",
                "path": "pages/page_1.png",
                "category": "pages",
                "name": "Page 2",
                "order": 2,
            },
        ],
        "characters": [
            {
                "id": "char001",
                "path": "characters/char_0.png",
                "category": "characters",
                "name": "Hero",
            },
        ],
        "references": [
            {
                "id": "ref001",
                "path": "input/reference_0.jpg",
                "category": "references",
                "name": "Photo 1",
            },
        ],
    }


@pytest.fixture
def project_json(working_folder: Path, sample_project_data: dict) -> Path:
    """Create a project.json file with sample data."""
    project_file = working_folder / "project.json"
    with open(project_file, "w") as f:
        json.dump(sample_project_data, f)
    return project_file


# =============================================================================
# Test Markers
# =============================================================================


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, mocked dependencies)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (NiceGUI User simulation)"
    )
