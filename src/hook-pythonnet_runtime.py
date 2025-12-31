# Runtime hook for pythonnet in PyInstaller
# This fixes "RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize"
# by telling pythonnet where to find the Python DLL in the frozen bundle.

import os
import sys
from glob import glob

if getattr(sys, 'frozen', False):
    # PyInstaller extracts to sys._MEIPASS
    base_dir = sys._MEIPASS
    
    # Find the python DLL (e.g., python311.dll) in the bundle
    # It is usually in the root of sys._MEIPASS
    dll_pattern = os.path.join(base_dir, "python*.dll")
    dll_files = glob(dll_pattern)
    
    if dll_files:
        # Set the environment variable that pythonnet checks
        os.environ["PYTHONNET_PYDLL"] = dll_files[0]
