# Runtime hook for pythonnet in PyInstaller
# This fixes "RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize"
# by telling pythonnet where to find the Python DLL in the frozen bundle.

import os
import sys
import glob

# Define a log function that writes to a file in the temp directory or next to exe
def log_debug(message):
    try:
        # Try to log to a file next to the executable
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        log_file = os.path.join(base_dir, "debug.log")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass # Fail silently if we can't write

def setup_pythonnet():
    if not getattr(sys, 'frozen', False):
        return

    log_debug("--- Initializing Python.NET Runtime Hook ---")
    log_debug(f"sys.executable: {sys.executable}")
    log_debug(f"sys.prefix: {sys.prefix}")
    
    # 1. Identify potential locations for python DLL
    search_dirs = []
    
    # PyInstaller 6+ / _internal folder
    exe_dir = os.path.dirname(sys.executable)
    internal_dir = os.path.join(exe_dir, "_internal")
    
    if os.path.exists(internal_dir):
        search_dirs.append(internal_dir)
    
    # Root folder (older PyInstaller or flat bundle)
    search_dirs.append(exe_dir)
    
    # sys._MEIPASS for OneFile (though we use OneDir, good for robustness)
    if hasattr(sys, '_MEIPASS'):
        search_dirs.append(sys._MEIPASS)
        
    log_debug(f"Search directories: {search_dirs}")

    python_dll = None
    
    for search_dir in search_dirs:
        # Look for python3*.dll
        pattern = os.path.join(search_dir, "python3*.dll")
        candidates = glob.glob(pattern)
        
        if candidates:
            log_debug(f"Found candidates in {search_dir}: {candidates}")
            
            # Prefer the most specific DLL (longest name), e.g. python311.dll over python3.dll
            # This avoids using the limited ABI shim if the full DLL is available
            candidates.sort(key=lambda x: len(os.path.basename(x)), reverse=True)
            
            python_dll = candidates[0]
            break
    
    if python_dll:
        log_debug(f"Setting PYTHONNET_PYDLL to: {python_dll}")
        os.environ["PYTHONNET_PYDLL"] = python_dll
    else:
        log_debug("CRITICAL: Could not find any python3*.dll in search directories!")
        
    log_debug("--- Hook finished ---")

if __name__ == "__main__":
    setup_pythonnet()
else:
    setup_pythonnet()
