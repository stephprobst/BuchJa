# Book Creator - Implementation Specification

> **Purpose**: This document serves as the implementation specification and guardrails for AI-assisted development. Follow these guidelines when implementing features.

## Project Overview

A standalone Windows desktop application built with NiceGUI that guides users through creating illustrated books using Google's Gemini (Nano Banana Pro) image generation API.

## Architecture

```
book_creator/
├── src/
│   ├── __init__.py
│   ├── main.py                    # NiceGUI app entry point (vertical tabs)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── settings.py            # API key & config management
│   │   ├── image_service.py       # Gemini API wrapper + rework support
│   │   ├── pdf_service.py         # PDF export with reportlab
│   │   ├── ai_config.py           # AI config loader (models & prompts)
│   │   ├── gemini_usage.py        # Usage tracking utilities
│   │   └── logging_config.py      # Logging configuration
│   └── components/
│       ├── __init__.py
│       ├── image_manager.py       # Image grid & management UI
│       ├── image_cropper.py       # NiceGUI wrapper for Vue cropper
│       ├── image_cropper.vue      # Cropper.js Vue component
│       ├── sketch_canvas.py       # NiceGUI wrapper for Vue canvas
│       ├── sketch_canvas.vue      # Fabric.js drawing component
│       └── status_footer.py       # Background task status footer
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Shared fixtures
│   ├── unit/                      # Fast, mocked service tests
│   │   ├── __init__.py
│   │   ├── test_settings.py
│   │   ├── test_image_service.py  # Includes rework tests
│   │   ├── test_image_cropper.py  # Cropper utility tests
│   │   ├── test_pdf_service.py
│   │   ├── test_ai_config_consistency.py
│   │   ├── test_gemini_usage.py
│   │   └── test_status_footer.py
│   └── integration/               # NiceGUI User simulation tests
│       ├── __init__.py
│       ├── test_settings_workflow.py
│       ├── test_image_workflow.py
│       ├── test_export_workflow.py
│       ├── test_tab_navigation.py # Tab switching & state preservation
│       └── test_usage_header.py
├── ai_config.json                 # AI model & prompt configuration
├── pyproject.toml                 # Dependencies & pytest config
├── SPEC.md                        # This file
└── README.md
```

## Dependencies

All dependencies use BSD/MIT/Apache-2.0 licenses suitable for commercial use:

| Package | License | Purpose |
|---------|---------|---------|
| `nicegui[native]` | MIT | GUI framework + desktop mode (pywebview) |
| `google-genai` | Apache-2.0 | Gemini API client |
| `pillow` | MIT-CMU | Image processing, thumbnails |
| `keyring` | MIT | Windows Credential Locker storage |
| `reportlab` | BSD | PDF generation |
| `pytest` | MIT | Unit testing framework |
| `pytest-asyncio` | Apache-2.0 | Async test support |
| `pytest-mock` | MIT | Mocking support for pytest |
| `nicegui` | MIT | Includes `nicegui.testing.User` used for UI simulation tests |

## GUI Workflow (Vertical Tabs)

The application uses vertical tabs (`ui.tabs` with `vertical=True`) for main navigation. Tab state is preserved during the session using `ui.tab_panels` with `keep-alive` prop.

### Tab Structure

| Tab | Icon | Purpose |
|-----|------|----------|
| **Settings** | `settings` | API key, working folder, aspect ratio, and style prompt |
| **Add** | `add_photo_alternate` | Upload references + crop elements from existing images |
| **Generate** | `auto_awesome` | Unified creation interface for new and reworked images |
| **Manage** | `folder` | Image organization and PDF export |

### Settings Tab
- API Key (stored in Windows Credential Locker via `keyring`)
- Working Folder selection
- Aspect Ratio dropdown
- Book Style prompt (applied to all generations)

### Add Tab
- **Upload Section**: Drag-drop or file picker for reference images
- **Crop Section**: Select any project image and crop a portion using Cropper.js
  - Supports rotation, flipping, and aspect ratio locking
  - Cropped images saved to `input/` as new references

### Generate Tab
- **Mode Toggle**: `Create` (new image) or `Rework` (modify existing)
- **Type Toggle**: `Character Sheet` or `Page`
- **Shared UI**: Single unified interface for all generation modes
  - Character sheet and reference image selection
  - Optional sketch canvas (Fabric.js)
  - Prompt input
- **Rework Mode**: Select source image, describe changes
  - Original preserved, new image saved with `rework_YYYYMMDD_HHMMSS_` prefix

### Manage Tab
- **Image Manager**: Tabbed grid (Pages/Characters/References)
  - View full-size images
  - Move between categories
  - Delete images
- **PDF Export**: Compile ordered pages into PDF

## Key Implementation Details

### Settings Service (`src/services/settings.py`)

```python
# API key stored securely via keyring
keyring.set_password("book_creator", "gemini_api_key", api_key)
api_key = keyring.get_password("book_creator", "gemini_api_key")

# Other settings in JSON config file (located in APPDATA)
{
    "working_folder": "C:/Users/.../MyBook",
    "aspect_ratio": "3:4",
    "style_prompt": "Whimsical children's book illustration style...",
    "gemini_usage": {
        "since": "2025-01-01T00:00:00+00:00",
        "totals": { "total_tokens": 1234, ... },
        "models": { ... }
    }
}
```

### Image Service (`src/services/image_service.py`)

- **Single request at a time**: Use `asyncio.Lock()` to prevent concurrent API calls
- **Thumbnails**: Generate 256px thumbnails in `thumbnails/` subfolder for UI display
- **Full resolution**: Store and send full-res images to API
- **System prompts**: Configured externally via `ai_config.json`
- **Usage tracking**: Reports token usage via callback for cost monitoring
- **Rework support**: Modify existing images while preserving originals

```python
class ImageService:
    def __init__(
        self,
        api_key: str,
        working_folder: Path,
        usage_callback: Optional[Callable[[GeminiUsage], None]] = None,
    ):
        self._lock = asyncio.Lock()
        self._client = genai.Client(api_key=api_key)
        self._working_folder = working_folder
        self._usage_callback = usage_callback
    
    async def generate_image(
        self,
        prompt: str,
        reference_images: list[Path] = None,
        sketch: Path = None,
        style_prompt: str = None,
        aspect_ratio: str = "3:4"
    ) -> tuple[Path, Path]:
        async with self._lock:
            # Build parts, call API, save result
            ...
    
    async def rework_image(
        self,
        original_image: Path,
        prompt: str,
        additional_references: list[Path] = None,
        sketch: Path = None,
        style_prompt: str = "",
        aspect_ratio: str = "3:4",
        category: str = "pages",
    ) -> tuple[Path, Path]:
        # Original image sent as first reference
        # New image saved with rework_YYYYMMDD_HHMMSS_originalname prefix
        ...
```

### AI Configuration (`src/services/ai_config.py` + `ai_config.json`)

Model names and system prompts are externalized to `ai_config.json` at the repository root:

```json
{
    "models": {
        "image_generation": "gemini-3-pro-image-preview"
    },
    "supported_models_for_usage_tracking": [
        "gemini-3-pro-image-preview"
    ],
    "system_prompts": {
        "character_sheet": "...",
        "page": "...",
        "rework_character": "...",
        "rework_page": "..."
    },
    "templates": {
        "style_prefix": "Style: {style_prompt}",
        "rework_instruction": "Original image is provided as the first reference. Requested changes: {prompt}"
    }
}
```

Override location via `BOOK_CREATOR_AI_CONFIG` environment variable.

### Custom Vue Drawing Component (Sketch Canvas)

Integrate Fabric.js as a NiceGUI custom Vue component for freehand sketching:

- Brush tool with size/color selection
- Eraser tool
- Clear canvas
- Export to PNG (saved to working folder)

### Custom Vue Image Cropper Component

Integrate Cropper.js as a NiceGUI custom Vue component for image cropping:

- Load any project image for cropping
- Rotation and flipping controls
- Aspect ratio selection (free, 1:1, 3:4, 4:3, 9:16, 16:9)
- Export cropped region to PNG
- Cropped images automatically registered as references

```python
# Usage from NiceGUI
from src.components.image_cropper import ImageCropper, save_cropped_image, image_to_data_url

cropper = ImageCropper(
    initial_aspect_ratio='free',
    on_crop=lambda data_url: save_cropped_image(data_url, output_path),
)

# Load an image into the cropper
cropper.load_image(image_to_data_url(source_path))
```

### Image Categories

Images are categorized and stored in `project.json`:

```json
{
    "pages": [
        {"id": "uuid", "path": "pages/page_001.png", "order": 1},
        {"id": "uuid", "path": "pages/page_002.png", "order": 2}
    ],
    "characters": [
        {"id": "uuid", "path": "characters/hero.png", "name": "Hero"}
    ],
    "references": [
        {"id": "uuid", "path": "references/photo1.jpg"}
    ]
}
```

### PDF Export (`src/services/pdf_service.py`)

Use `reportlab` (BSD license) to create PDF:

```python
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def export_to_pdf(pages: list[Path], output_path: Path, aspect_ratio: str):
    # Calculate page dimensions from aspect ratio
    # Add each image as a full-page spread
    ...
```

## Testing Strategy

### Unit Tests (`tests/unit/`)

- **Mock all external dependencies** (API calls, file system where appropriate)
- Focus on business logic correctness
- Fast execution (< 1 second per test)
- Target 80%+ coverage on services

```python
# Example: test_image_service.py
@pytest.fixture
def mock_genai_client(mocker):
    """Mock the Gemini API client to avoid real API calls"""
    mock_client = mocker.Mock()
    mock_client.models.generate_content_stream.return_value = [
        # Mock response chunks
    ]
    return mock_client
```

### Integration Tests (`tests/integration/`)

- **Use NiceGUI's `User` testing class** from `pytest-nicegui`
- Simulate complete user workflows via button clicks and input
- **No visual regression / screenshots** - only simulated interactions
- **Mock API calls** to avoid token usage and costs
- Focus on UI state changes and workflow correctness

```python
# Example: test_settings_workflow.py
async def test_save_api_key(user: User, mocker):
    """Test that API key can be saved via settings panel"""
    mock_keyring = mocker.patch('keyring.set_password')
    
    await user.open('/')
    await user.should_see('Settings')
    user.find('Settings').click()
    
    api_key_input = user.find(marker='api-key-input')
    api_key_input.type('test-api-key-12345')
    
    user.find('Save Settings').click()
    
    mock_keyring.assert_called_once_with(
        "book_creator", "gemini_api_key", "test-api-key-12345"
    )
```

### Test Execution

```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=src --cov-report=html
```

## Bundling for Windows

Use `nicegui-pack` to create standalone executable:

```bash
nicegui-pack --onedir --windowed --name "BookCreator" src/main.py
```

**Requirements**:
- .NET Framework (typically pre-installed on Windows)
- WebView2 runtime (auto-installed by pywebview)

**Output**: `dist/BookCreator/` directory with `BookCreator.exe`

## Coding Guidelines

1. **Type hints**: Use type hints for all function signatures
2. **Async**: Use async/await for I/O operations (API calls, file operations)
3. **Error handling**: Wrap API calls in try/except, show user-friendly error messages
4. **Logging**: Use `logging` module for debugging (not print statements)
5. **Path handling**: Use `pathlib.Path` instead of string paths
6. **Constants**: Define magic strings/numbers as module-level constants

## System Prompts

System prompts are configured in `ai_config.json` (see AI Configuration section above). The following prompts are defined:

| Key | Purpose |
|-----|---------|  
| `character_sheet` | Character reference sheets with multiple angles |
| `page` | Full-page book illustrations with continuity |
| `rework_character` | Refine existing character sheet based on instructions |
| `rework_page` | Refine existing page illustration based on instructions |

## File Organization in Working Folder

```
MyBook/                          # User's working folder
├── input/                       # Drop zone for reference photos
├── characters/                  # Generated character sheets
├── pages/                       # Generated book pages
├── sketches/                    # User-created sketches
├── thumbnails/                  # 256px thumbnails for UI
├── logs/                        # Application log files
│   └── book_creator.log         # Rotating log file
├── project.json                 # Project metadata
└── exports/                     # PDF exports
```
