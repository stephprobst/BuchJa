"""Build script for Book Creator application.

This script handles:
1. License compliance checking (fails on GPL/LGPL/AGPL)
2. THIRD-PARTY-LICENSES.txt generation for bundled dependencies
3. Building Windows executable using NiceGUI's pack feature

Requires: uv (https://docs.astral.sh/uv/)
"""

import datetime
import glob
import os
import shutil
import subprocess
import sys


def run_command(command: str) -> None:
    """Runs a shell command and exits if it fails."""
    print(f"🚀 Running: {command}")
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError:
        print(f"❌ Error executing: {command}")
        sys.exit(1)


def main():
    print("--- STARTING BUILD ---")

    # 1. CLEAN: Remove dev dependencies from environment
    #    This ensures pip-licenses only sees runtime dependencies.
    print("\n--- STEP 1: Stripping Dev Dependencies ---")
    run_command("uv sync --no-dev")

    # 2. AUDIT: Check for banned licenses (GPL, etc.)
    #    If this fails, the build stops immediately.
    print("\n--- STEP 2: Checking License Compliance ---")
    run_command('uv run --with pip-licenses pip-licenses --fail-on "GPL;LGPL;AGPL"')

    # 3. GENERATE: Create the THIRD-PARTY-LICENSES.txt file
    print("\n--- STEP 3: Generating THIRD-PARTY-LICENSES.txt ---")
    run_command((
        'uv run --with pip-licenses pip-licenses '
        '--from=mixed '
        '--with-system '
        '--with-urls '
        '--with-license-file '
        '--no-license-path '
        '--output-file=THIRD-PARTY-LICENSES.txt '
        '--ignore-packages pip-licenses PTable wcwidth prettytable'
    ))

    print("Appending verification timestamp...")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    disclaimer_text = f"""
    
================================================================================
LICENSE COMPLIANCE SNAPSHOT
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

    # 4. RESTORE: Bring back build tools (includes pyinstaller for nicegui-pack)
    print("\n--- STEP 4: Restoring Build Tools ---")
    run_command("uv sync --extra bundle")

    # 5. BUILD: Create the executable using NiceGUI pack
    print("\n--- STEP 5: Building Windows Executable ---")
    run_command((
        'uv run nicegui-pack '
        '--name "Book Creator" '
        '--onefile '
        '--windowed '
        '--add-data "ai_config.json;." '
        'src/main.py'
    ))

    # 6. COPY LICENSE FILES: Place alongside executable
    print("\n--- STEP 6: Copying License Files to dist/ ---")
    os.makedirs("dist", exist_ok=True)
    shutil.copy("LICENSE", "dist/LICENSE")
    shutil.copy("THIRD-PARTY-LICENSES.txt", "dist/THIRD-PARTY-LICENSES.txt")
    shutil.copy("NOTICE.md", "dist/NOTICE.md")
    shutil.copy("SECURITY.md", "dist/SECURITY.md")

    # 7. CLEANUP: Remove PyInstaller artifacts
    print("\n--- STEP 7: Cleaning Up ---")
    for spec_file in glob.glob("*.spec"):
        print(f"Removing {spec_file}")
        os.remove(spec_file)

    print("\n✅ BUILD SUCCESSFUL!")
    print("   dist/")
    print("   ├── Book Creator.exe")
    print("   ├── LICENSE")
    print("   ├── NOTICE.md")
    print("   ├── SECURITY.md")
    print("   └── THIRD-PARTY-LICENSES.txt")
if __name__ == "__main__":
    main()