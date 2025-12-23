# Contributing to BuchJa

Thank you for your interest in contributing to BuchJa! This document provides instructions for setting up your development environment, running tests, and building the application.

## Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Development Setup

### Install Dependencies

**Runtime dependencies only:**
```bash
uv sync --no-dev
```

**All dependencies (including dev tools for testing):**
```bash
uv sync
```

**With build tools (for creating executables):**
```bash
uv sync --extra bundle
```

### Pinned Dependencies

All dependencies are pinned in `uv.lock`. The `uv sync` command automatically uses these pinned versions to ensure reproducible builds and license compliance.

To update dependencies to their latest compatible versions:
```bash
uv lock --upgrade
uv sync
```

## Running the Application (Development Mode)

```bash
uv run BuchJa
```

## Running Tests

```bash
uv run python -m pytest
```

Run with coverage and update badge:
```bash
uv run python -m pytest --cov=src --cov-report=xml
uv run genbadge coverage -i coverage.xml -o badges/coverage.svg
```

## Building for Distribution

### Build Windows Executable

Run the build script:
```bash
uv run python build.py
```

This will:
1. Strip dev dependencies to audit only runtime packages
2. Check license compliance (fails on GPL/LGPL/AGPL)
3. Generate `THIRD-PARTY-LICENSES.txt` with all dependency licenses
4. Build a Windows executable using NiceGUI's pack feature and bundle it with the required markdown files.

The executable will be created in the `dist/` folder.

## License Compliance

The build script automatically checks that no GPL, LGPL, or AGPL licensed packages are included in the runtime dependencies. This ensures the application can be distributed under the MIT license.

To manually check license compliance:
```bash
uv run --with pip-licenses pip-licenses --fail-on "GPL;LGPL;AGPL"
```
