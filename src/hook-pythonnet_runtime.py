# Runtime hook for pythonnet in PyInstaller
# This fixes "RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize"
# by telling pythonnet where to find the Python DLL and Runtime assembly in the frozen bundle.
#
# This hook runs very early during app startup, before any imports.
# It sets up environment variables that pythonnet/clr_loader need to find their DLLs.

import os
import sys
import glob
import ctypes

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

def _check_dotnet_framework():
    """Check if .NET Framework 4.6.1+ is available."""
    if sys.platform != 'win32':
        return False, "Not on Windows"
    
    try:
        import winreg
        # Check for .NET Framework 4.6.1+ (release key >= 394254)
        key_path = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            release, _ = winreg.QueryValueEx(key, "Release")
            if release >= 394254:  # .NET Framework 4.6.1
                return True, f"Release {release}"
            else:
                return False, f"Release {release} is too old (need >= 394254 for 4.6.1+)"
    except Exception as e:
        return False, f"Registry check failed: {e}"

def setup_pythonnet():
    if not getattr(sys, 'frozen', False):
        return

    log_debug("=" * 60)
    log_debug("--- Initializing Python.NET Runtime Hook ---")
    log_debug(f"sys.executable: {sys.executable}")
    log_debug(f"sys.prefix: {sys.prefix}")
    log_debug(f"sys.platform: {sys.platform}")
    log_debug(f"64-bit: {sys.maxsize > 2**32}")
    
    # Check .NET Framework availability
    dotnet_ok, dotnet_info = _check_dotnet_framework()
    log_debug(f".NET Framework check: {dotnet_ok} - {dotnet_info}")
    
    # Identify the base directory for bundled files
    exe_dir = os.path.dirname(sys.executable)
    internal_dir = os.path.join(exe_dir, "_internal")
    
    # Use _MEIPASS if available (onefile mode), otherwise use _internal (onedir mode)
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    elif os.path.exists(internal_dir):
        base_dir = internal_dir
    else:
        base_dir = exe_dir
    
    log_debug(f"Base directory for bundled files: {base_dir}")
    
    # 1. Find the Python.Runtime.dll location and set working directory
    #    The .NET CLR looks for dependencies relative to the working directory and assembly location
    pythonnet_runtime_dir = os.path.join(base_dir, "pythonnet", "runtime")
    runtime_dll = os.path.join(pythonnet_runtime_dir, "Python.Runtime.dll")
    
    if os.path.exists(runtime_dll):
        log_debug(f"Found Python.Runtime.dll at: {runtime_dll}")
        
        # Change working directory to help .NET find dependencies
        original_cwd = os.getcwd()
        log_debug(f"Original working directory: {original_cwd}")
        log_debug(f"Setting working directory to: {pythonnet_runtime_dir}")
        os.chdir(pythonnet_runtime_dir)
    else:
        log_debug("WARNING: Could not find Python.Runtime.dll in expected location!")
        log_debug(f"Searched: {runtime_dll}")
    
    # 2. Identify potential locations for python DLL
    search_dirs = [base_dir, exe_dir]
        
    log_debug(f"Search directories for Python DLL: {search_dirs}")

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
        
        # Add DLL directory to PATH to ensure dependencies are found
        dll_dir = os.path.dirname(python_dll)
        current_path = os.environ.get("PATH", "")
        if dll_dir not in current_path:
            log_debug(f"Adding {dll_dir} to PATH")
            os.environ["PATH"] = dll_dir + os.pathsep + current_path
    else:
        log_debug("CRITICAL: Could not find any python3*.dll in search directories!")
    
    # 3. Also add the pythonnet runtime directory to PATH for .NET assembly resolution
    pythonnet_runtime_dir = os.path.join(base_dir, "pythonnet", "runtime")
    if os.path.exists(pythonnet_runtime_dir):
        current_path = os.environ.get("PATH", "")
        if pythonnet_runtime_dir not in current_path:
            log_debug(f"Adding pythonnet runtime dir to PATH: {pythonnet_runtime_dir}")
            os.environ["PATH"] = pythonnet_runtime_dir + os.pathsep + current_path
    
    # 4. Add clr_loader FFI dlls directory to PATH (contains ClrLoader.dll for .NET Framework)
    clr_loader_ffi_dir = os.path.join(base_dir, "clr_loader", "ffi", "dlls")
    if sys.maxsize > 2**32:
        clr_loader_ffi_dir = os.path.join(clr_loader_ffi_dir, "amd64")
    else:
        clr_loader_ffi_dir = os.path.join(clr_loader_ffi_dir, "x86")
    
    if os.path.exists(clr_loader_ffi_dir):
        current_path = os.environ.get("PATH", "")
        if clr_loader_ffi_dir not in current_path:
            log_debug(f"Adding clr_loader ffi dir to PATH: {clr_loader_ffi_dir}")
            os.environ["PATH"] = clr_loader_ffi_dir + os.pathsep + current_path
    else:
        log_debug(f"WARNING: clr_loader ffi dir not found at: {clr_loader_ffi_dir}")
    
    # 5. Add the base _internal directory to PATH for general DLL resolution
    current_path = os.environ.get("PATH", "")
    if base_dir not in current_path:
        log_debug(f"Adding base dir to PATH: {base_dir}")
        os.environ["PATH"] = base_dir + os.pathsep + current_path
        
    log_debug("--- Hook finished ---")

if __name__ == "__main__":
    setup_pythonnet()
else:
    setup_pythonnet()
