# Book Creator

A NiceGUI-based desktop application for creating illustrated books using Google's Gemini image generation API.

## Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

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

## Running the Application

```bash
uv run book-creator
```

## Development

### Running Tests

```bash
uv run python -m pytest
```

Run with coverage:
```bash
uv run python -m pytest --cov=src
```

### Code Structure

- `src/` - Main application source code
  - `main.py` - Application entry point
  - `components/` - UI components
  - `services/` - Business logic and API services
- `tests/` - Test suite
  - `unit/` - Unit tests
  - `integration/` - Integration tests

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

## License and Security Information

### This Project

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for the full text. Also see the `NOTICE.md` file for additional licensing and attribution information as well as the `SECURITY.md` file for information on security practices.

### Third-Party Dependencies

License information for all dependencies is available in multiple places:

| Location | Description |
|----------|-------------|
| `THIRD-PARTY-LICENSES.txt` | Generated during build, lists all runtime dependencies with licenses |
| `uv.lock` | Contains package metadata including license info |
| `pyproject.toml` | Lists direct dependencies |

**In the distributed files:**

The LICENSE file, the NOTICE.md file, the THIRD-PARTY-LICENSES.txt file and the SECURITY.md file are included in the root of the packaged application distribution.

### License Compliance

The build script automatically checks that no GPL, LGPL, or AGPL licensed packages are included in the runtime dependencies. This ensures the application can be distributed under the MIT license.

To manually check license compliance:
```bash
uv run --with pip-licenses pip-licenses --fail-on "GPL;LGPL;AGPL"
```
