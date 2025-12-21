# Book Creator

Create illustrated books with AI image generation using Google's Gemini API.

## Quick Start

```powershell
# Install uv (once)
pip install uv

# Sync locked dependencies
uv sync --extra dev

# Run the application
python -m src.main
```

Configure your Gemini API key in the Settings panel.

## Development

```powershell
# Run all tests
pytest

# Run unit tests only (fast)
pytest tests/unit/

# Run with coverage
pytest --cov=src --cov-report=html

# Update lock file after changing pyproject.toml
uv lock
```

## Building for Distribution

```powershell
# Sync with bundle dependencies
uv sync --extra bundle

# Build using PyInstaller spec file
pyinstaller book_creator.spec

# Or use nicegui-pack
nicegui-pack build.toml
```

The built application will be in `dist/BookCreator/`.