# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Book Creator.

This file is used by PyInstaller (via nicegui-pack) to bundle the application.
Run with: nicegui-pack build.toml
Or directly: pyinstaller book_creator.spec
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))

# Analysis configuration
a = Analysis(
    ['src/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Include Vue components
        ('src/components/*.vue', 'src/components'),
        # Include AI config
        ('ai_config.json', '.'),
    ],
    hiddenimports=[
        # NiceGUI and webview
        'nicegui',
        'nicegui.elements',
        'nicegui.native',
        'webview',
        'webview.platforms.winforms',
        
        # Image processing
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        
        # PDF generation
        'reportlab',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.units',
        'reportlab.pdfgen',
        'reportlab.pdfgen.canvas',
        
        # Secure storage
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        
        # Google AI
        'google.genai',
        'google.genai.types',
        
        # Async support
        'asyncio',
        'aiofiles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib', 
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Create PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BookCreator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment when icon is available
)

# Collect all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BookCreator',
)
