"""Build script for BuchJa application.

This script handles:
1. License compliance checking (fails on GPL/LGPL/AGPL)
2. THIRD-PARTY-LICENSES.txt generation for bundled dependencies
3. Building Windows executable using PyInstaller

Requires: uv (https://docs.astral.sh/uv/)
"""

import argparse
import datetime
import glob
import os
import shutil
import subprocess
import sys
import tomllib


def get_version() -> str:
    """Reads the version from pyproject.toml."""
    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def run_command(command: str) -> None:
    """Runs a shell command and exits if it fails."""
    print(f"🚀 Running: {command}")
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError:
        print(f"❌ Error executing: {command}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Build script for BuchJa")
    parser.add_argument(
        "--tests",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run tests and update coverage badge (default: True)",
    )
    args = parser.parse_args()

    print(f"--- STARTING BUILD (Tests: {args.tests}) ---")

    # 1. BADGE: Update coverage badge
    #    This requires dev dependencies, so we sync them first.
    if args.tests:
        print("\n--- STEP 1: Updating Coverage Badge ---")
        run_command("uv sync")
        print("Running tests... (Build will stop if tests fail)")
        run_command("uv run python -m pytest --cov=src --cov-report=xml")
        if not os.path.exists("badges"):
            os.makedirs("badges")
        run_command("uv run genbadge coverage -i coverage.xml -o badges/coverage.svg")
    else:
        print("\n--- STEP 1: Skipping Tests and Coverage Badge ---")

    # 2. CLEAN: Remove dev dependencies from environment
    #    This ensures pip-licenses only sees runtime dependencies.
    print("\n--- STEP 2: Stripping Dev Dependencies ---")
    run_command("uv sync --no-dev")

    # 3. AUDIT: Check for banned licenses (GPL, etc.)
    #    If this fails, the build stops immediately.
    print("\n--- STEP 3: Checking License Compliance ---")
    run_command(
        'uv run --no-dev --with pip-licenses pip-licenses --fail-on "GPL;LGPL;AGPL"'
    )

    # 4. GENERATE: Create the THIRD-PARTY-LICENSES.txt file
    print("\n--- STEP 4: Generating THIRD-PARTY-LICENSES.txt ---")
    run_command(
        (
            "uv run --no-dev --with pip-licenses pip-licenses "
            "--from=mixed "
            "--with-system "
            "--with-urls "
            "--with-license-file "
            "--no-license-path "
            "--output-file=THIRD-PARTY-LICENSES.txt "
            "--ignore-packages pip-licenses PTable wcwidth prettytable"
        )
    )

    print("Appending verification timestamp...")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    disclaimer_text = f"""

    
================================================================================
LICENSE COMPLIANCE SNAPSHOT (PYTHON DEPENDENCIES)
================================================================================
This license file was automatically generated during the build process.
Verification Timestamp: {timestamp}

The author has exercised due diligence to ensure these dependencies are 
compatible with the project's MIT license. However, the end user is 
responsible for verifying compliance if this software is modified or 
redistributed.
================================================================================
"""
    with open("THIRD-PARTY-LICENSES.txt", "a", encoding="utf-8") as f:
        f.write(disclaimer_text)

    # --- FRONTEND LICENSES ---
    # These are JavaScript libraries bundled with NiceGUI or loaded dynamically.
    # Since they are not Python packages, pip-licenses cannot detect them.
    # We manually append their licenses here to ensure compliance.

    js_licenses = """


================================================================================
FRONTEND & JAVASCRIPT DEPENDENCIES
================================================================================
The following libraries are bundled within the application's user interface 
layer. These are JavaScript dependencies not tracked by the Python package manager.
Below license texts have been copied from their respective official repositories,
and compliance with the MIT license has been manually verified on 2025-12-21.

--------------------------------------------------------------------------------
Name: Vue.js
License: MIT
Copyright (c) 2018-present, Yuxi (Evan) You and Vue contributors
--------------------------------------------------------------------------------
The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

--------------------------------------------------------------------------------
Name: Quasar Framework
License: MIT
Copyright (c) 2015-present Razvan Stoenescu
--------------------------------------------------------------------------------
The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

--------------------------------------------------------------------------------
Name: Cropper.js (v1.6.1)
License: MIT
Copyright 2015-present Chen Fengyuan
--------------------------------------------------------------------------------
The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

--------------------------------------------------------------------------------
Name: Fabric.js (v5.3.1)
License: MIT
Copyright (c) 2008-2015 Printio (Juriy Zaytsev, Maxim Chernyak)
--------------------------------------------------------------------------------
The MIT License (MIT)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

    with open("THIRD-PARTY-LICENSES.txt", "a", encoding="utf-8") as f:
        f.write(js_licenses)

    # 5. RESTORE: Bring back build tools (includes pyinstaller)
    print("\n--- STEP 5: Restoring Build Tools ---")
    run_command("uv sync --extra bundle")

    # 6. BUILD: Create the executable using PyInstaller
    print("\n--- STEP 6: Building Windows Executable ---")

    pyinstaller_cmd = (
        "uv run pyinstaller "
        '--name "BuchJa" '
        "--onedir "
        "--noconfirm "
        "--clean "
        "--console "
        '--add-data "ai_config.json;." '
        '--add-data "src/materials;materials" '
        '--add-data "src/components/image_cropper.vue;src/components" '
        '--add-data "src/components/sketch_canvas.vue;src/components" '
        '--icon "src/materials/logo.png" '
        "src/main.py"
    )

    run_command(pyinstaller_cmd)

    # 7. COPY LICENSE FILES: Place alongside executable
    print("\n--- STEP 7: Copying License Files to dist/ ---")
    os.makedirs("dist", exist_ok=True)
    shutil.copy("LICENSE", "dist/BuchJa/LICENSE")
    shutil.copy("THIRD-PARTY-LICENSES.txt", "dist/BuchJa/THIRD-PARTY-LICENSES.txt")
    shutil.copy("NOTICE.md", "dist/BuchJa/NOTICE.md")
    shutil.copy("SECURITY.md", "dist/BuchJa/SECURITY.md")

    # 8. CLEANUP: Remove PyInstaller artifacts
    print("\n--- STEP 8: Cleaning Up ---")
    for spec_file in glob.glob("*.spec"):
        print(f"Removing {spec_file}")
        os.remove(spec_file)

    print("\n✅ BUILD SUCCESSFUL!")
    print("   dist/BuchJa/")
    print("   ├── BuchJa.exe")
    print("   ├── _internal")
    print("   ├── LICENSE")
    print("   ├── NOTICE.md")
    print("   ├── SECURITY.md")
    print("   └── THIRD-PARTY-LICENSES.txt")

    # 9. ZIP: Archive the output
    print("\n--- STEP 9: Zipping Output ---")
    version = get_version()
    zip_name = f"BuchJa_v{version}"

    # Create zip in dist/ folder, containing the BuchJa folder
    shutil.make_archive(os.path.join("dist", zip_name), "zip", "dist", "BuchJa")
    print(f"   Created dist/{zip_name}.zip")


if __name__ == "__main__":
    main()
