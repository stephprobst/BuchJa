import subprocess
import sys
import os

def run_command(command):
    """Runs a shell command and exits if it fails"""
    print(f"🚀 Running: {command}")
    try:
        # shell=True is required for Windows to interpret commands correctly
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError:
        print(f"❌ Error executing: {command}")
        sys.exit(1)

def main():
    print("--- STARTING SAFE BUILD ---")

    # 1. CLEAN: Remove dev dependencies (PyInstaller, etc.) from environment
    #    This ensures pip-licenses only sees what users actually run.
    print("\n--- STEP 1: Stripping Dev Dependencies ---")
    run_command("uv sync --no-dev")

    # 2. AUDIT: Check for banned licenses (GPL, etc.)
    #    If this fails, the build stops immediately.
    print("\n--- STEP 2: Checking License Compliance ---")
    # We install pip-licenses ephemerally using `uv run --with`
    run_command('uv run --with pip-licenses pip-licenses --fail-on "GPL;LGPL;AGPL"')

    # 3. GENERATE: Create the CREDITS.txt file
    print("\n--- STEP 3: Generating CREDITS.txt ---")
    # We ignore pip-licenses and its dependencies (PTable, wcwidth) 
    # so they don't appear in your app's credits.
    run_command((
        'uv run --with pip-licenses pip-licenses '
        '--from=mixed '
        '--with-system '
        '--with-urls '
        '--with-license-file '
        '--no-license-path '
        '--output-file=CREDITS.txt '
        '--ignore-packages pip-licenses PTable wcwidth'
    ))

    # 4. RESTORE: Bring back build tools (PyInstaller)
    print("\n--- STEP 4: Restoring Build Tools ---")
    run_command("uv sync")

    # 5. BUILD: Create the executable
    print("\n--- STEP 5: Building Executable ---")
    
    # Windows Separator for --add-data is semicolon (;)
    # Format: source;destination
    add_data_arg = "CREDITS.txt;."
    
    run_command(f'uv run pyinstaller --noconfirm --onefile --windowed --add-data "{add_data_arg}" main.py')

    print("\n✅ BUILD SUCCESSFUL! Check the /dist folder.")

if __name__ == "__main__":
    main()