"""BuchJa - Main Application Entry Point."""

import sys
import os

# Workaround: Redirect stdout/stderr to devnull if running in windowed mode (no console)
# This prevents "Invalid Handle" crashes when libraries try to print logs.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")


def check_dependencies():
    """Checks for required system dependencies (Visual C++ Redistributable)."""
    if os.name != "nt":
        return

    import ctypes
    import winreg
    import webbrowser

    try:
        # Check for Visual C++ 2015-2022 Redistributable
        is_64bits = sys.maxsize > 2**32
        arch = "x64" if is_64bits else "x86"
        key_path = f"SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\{arch}"

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ
            ) as key:
                installed, _ = winreg.QueryValueEx(key, "Installed")
                if installed == 1:
                    return
        except OSError:
            pass  # Key not found

        # If we get here, the registry key was missing or Installed != 1
        MB_ICONERROR = 0x10
        MB_YESNO = 0x04
        IDYES = 6

        title = "Missing System Component"
        message = (
            "The Microsoft Visual C++ Redistributable is missing.\n"
            "This component is required for BuchJa to run.\n\n"
            "Click 'Yes' to open the official Microsoft download page.\n"
            "Please download and install the 'x64' version manually to continue."
        )

        # Show native message box
        result = ctypes.windll.user32.MessageBoxW(
            0, message, title, MB_ICONERROR | MB_YESNO
        )

        if result == IDYES:
            # Open Microsoft's download page
            webbrowser.open(
                "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170"
            )

        sys.exit(1)

    except Exception as e:
        # If checking fails, log it but try to continue
        # Note: stderr might be redirected to devnull above
        try:
            print(f"Dependency check failed: {e}", file=sys.stderr)
        except:
            pass


check_dependencies()


import logging
import socket
from nicegui import ui
from nicegui import app
from pathlib import Path
from src.app import APP, init_services, init_image_service
from src._utils import (
    start_folder_watcher,
    usage_text,
    usage_tooltip_text,
    tooltip_html_from_text,
)
from src.components.status_footer import StatusFooter
from src.tabs.settings import build_settings_tab
from src.tabs.add import build_add_tab
from src.tabs.crop import build_crop_tab
from src.tabs.generate import build_generate_tab
from src.tabs.sketch import build_sketch_tab
from src.tabs.instructions import build_instructions_tab
from src.tabs.manage import build_manage_tab
from src.tabs.export import build_export_tab

logger = logging.getLogger(__name__)

# Set native window icon (taskbar icon on Windows)
# This must be at module level to be picked up by the subprocess on Windows
logo_path = Path(__file__).parent / "materials" / "logo.png"
if not logo_path.exists():
    raise FileNotFoundError(f"Icon file not found: {logo_path}")

app.native.start_args["icon"] = str(logo_path)


@ui.page("/")
def main_page():
    """Main application page with vertical tab navigation."""
    # Add custom styles
    ui.add_head_html("""
        <style>
            .q-uploader__file {
                background-size: contain !important;
                background-repeat: no-repeat !important;
                background-position: center !important;
                background-color: #f3f4f6 !important;
            }
            .q-uploader__file-img {
                background-size: contain !important;
                background-repeat: no-repeat !important;
                background-position: center !important;
                background-color: #f3f4f6 !important;
            }
            /* Vertical tabs styling */
            .vertical-tabs .q-tabs--vertical .q-tab {
                justify-content: center;
                padding: 12px 16px;
            }
        </style>
    """)

    # Initialize services
    init_services()
    if init_image_service():
        start_folder_watcher()

    # Header
    with ui.header().classes("bg-primary items-center"):
        with ui.row().classes("items-center gap-2"):
            ui.image(logo_path).classes("w-12 h-12")
            ui.label("BuchJa").classes("text-2xl font-bold text-white")
            ui.label("Create illustrated books with AI").classes(
                "text-white opacity-80 ml-4"
            )
        ui.space()

        with ui.row().classes("items-center gap-4"):
            tokens_text, since_text, cost_text, has_cost = usage_text()
            total_only = tokens_text

            usage_tokens_label = ui.label(total_only).classes("text-white")
            usage_tokens_label._props["marker"] = "gemini-usage-tokens"
            with usage_tokens_label:
                with ui.tooltip():
                    usage_tooltip_html = ui.html(
                        tooltip_html_from_text(usage_tooltip_text()),
                        sanitize=False,
                    )

            usage_since_label = ui.label(since_text).classes(
                "text-white opacity-80 text-sm"
            )
            usage_since_label._props["marker"] = "gemini-usage-since"

            usage_cost_label = ui.label(cost_text or "").classes("text-white")
            usage_cost_label._props["marker"] = "gemini-usage-cost"
            usage_cost_label.set_visibility(has_cost)

            def refresh_usage_labels() -> None:
                t, s, c, has = usage_text()
                usage_tokens_label.text = t
                usage_tooltip_html.content = tooltip_html_from_text(
                    usage_tooltip_text()
                )
                usage_since_label.text = s
                usage_cost_label.text = c or ""
                usage_cost_label.set_visibility(has)

            def reset_usage() -> None:
                if APP.settings is None:
                    return
                APP.settings.reset_gemini_usage()
                refresh_usage_labels()

            reset_btn = (
                ui.button(icon="restart_alt", on_click=reset_usage)
                .props("flat dense round")
                .classes("text-white")
            )
            reset_btn._props["marker"] = "gemini-usage-reset-btn"
            reset_btn.tooltip("Reset Gemini usage counters")

            ui.timer(1.0, refresh_usage_labels)

    # Main content with vertical tabs
    with ui.element("div").classes("flex w-full h-full"):
        # Vertical tabs on the left
        with ui.element("div").classes("vertical-tabs"):
            with ui.tabs().props("vertical").classes("bg-gray-100 h-full") as tabs:
                instructions_tab = ui.tab("Instructions", icon="help")
                instructions_tab._props["marker"] = "tab-instructions"
                settings_tab = ui.tab("Settings", icon="settings")
                settings_tab._props["marker"] = "tab-settings"
                add_tab = ui.tab("Add", icon="add_photo_alternate")
                add_tab._props["marker"] = "tab-add"
                crop_tab = ui.tab("Crop", icon="crop")
                crop_tab._props["marker"] = "tab-crop"
                sketch_tab = ui.tab("Sketch", icon="brush")
                sketch_tab._props["marker"] = "tab-sketch"
                generate_tab = ui.tab("Generate", icon="auto_awesome")
                generate_tab._props["marker"] = "tab-generate"
                manage_tab = ui.tab("Manage", icon="folder")
                manage_tab._props["marker"] = "tab-manage"
                export_tab = ui.tab("Export", icon="picture_as_pdf")
                export_tab._props["marker"] = "tab-export"

            # Handle tab changes to warn about unsaved settings
            current_tab = "Instructions"

            # Create dialog once
            with ui.dialog() as dirty_dialog, ui.card():
                ui.label("You have unsaved settings. Do you really want to leave?")
                with ui.row().classes("w-full justify-end"):
                    ui.button("Stay", on_click=lambda: dirty_dialog.submit("Stay"))
                    ui.button(
                        "Leave", on_click=lambda: dirty_dialog.submit("Leave")
                    ).props("color=red")

            async def on_tab_change(e):
                nonlocal current_tab
                new_tab = e.value

                # If we are moving away from settings
                if current_tab == "Settings" and new_tab != "Settings":
                    if APP.check_settings_dirty and APP.check_settings_dirty():
                        # Revert immediately to prevent navigation
                        tabs.value = "Settings"

                        dirty_dialog.open()
                        result = await dirty_dialog
                        if result == "Leave":
                            # User confirmed leaving, allow the change
                            current_tab = new_tab
                            tabs.value = new_tab
                        return

                current_tab = new_tab

            tabs.on_value_change(on_tab_change)

        # Tab panels on the right (with keep-alive for state preservation)
        with (
            ui.tab_panels(tabs, value=instructions_tab)
            .props("keep-alive")
            .classes("flex-1 overflow-auto")
        ):
            with ui.tab_panel(instructions_tab):
                build_instructions_tab()

            with ui.tab_panel(settings_tab):
                build_settings_tab()

            with ui.tab_panel(add_tab):
                build_add_tab()

            with ui.tab_panel(crop_tab):
                build_crop_tab()

            with ui.tab_panel(sketch_tab):
                build_sketch_tab()

            with ui.tab_panel(generate_tab):
                build_generate_tab()

            with ui.tab_panel(manage_tab):
                build_manage_tab()

            with ui.tab_panel(export_tab):
                build_export_tab()

    # Status footer
    APP.status_footer = StatusFooter()


def _check_webview2_available() -> bool:
    """Check if Microsoft Edge WebView2 Runtime is available on Windows."""
    if sys.platform != "win32":
        return True

    try:
        import winreg

        # GUID for WebView2 Runtime
        webview2_key = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        webview2_key_64 = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

        paths_to_check = [
            (winreg.HKEY_LOCAL_MACHINE, webview2_key_64),
            (winreg.HKEY_LOCAL_MACHINE, webview2_key),
            (winreg.HKEY_CURRENT_USER, webview2_key),
        ]

        for hkey, path in paths_to_check:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    # Read the 'pv' (Product Version) value
                    version, _ = winreg.QueryValueEx(key, "pv")
                    # Version must be present and not 0.0.0.0
                    if version and version != "0.0.0.0":
                        return True
            except FileNotFoundError:
                continue

        return False
    except Exception:
        # If we can't check, assume it's available
        return True


def _find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def main():
    """Application entry point."""

    # Prevent infinite spawning in multiprocessing environments (crucial for PyInstaller)
    import multiprocessing

    multiprocessing.freeze_support()

    try:
        import pyi_splash  # Cannot be resolved as included during bundling from pyinstaller.

        pyi_splash.update_text("Buch Jaaaa. Buch gut! Buch Ja!")
        pyi_splash.close()
    except ImportError:
        pass

    # Check if WebView2 is available for native mode
    native_mode = True
    if getattr(sys, "frozen", False) and not _check_webview2_available():
        logger.warning("WebView2 Runtime not found, falling back to browser mode")
        native_mode = False

    # Dynamic Port Selection to prevent conflicts
    port = _find_free_port()

    def shutdown():
        """Ensure clean shutdown of the application."""
        logger.info("Shutting down application...")

        # Stop folder watcher if running
        if APP.folder_watcher_timer:
            try:
                APP.folder_watcher_timer.cancel()
            except Exception:
                pass

        # Force exit to prevent zombie processes
        # This is crucial for the native window mode
        import os

        os._exit(0)

    app.on_shutdown(shutdown)

    # If in browser mode (fallback), shut down when the client disconnects (tab closed)
    if not native_mode:
        app.on_disconnect(app.shutdown)

    ui.run(
        title="BuchJa",
        native=native_mode,
        reload=False,
        favicon=logo_path,
        window_size=(1200, 1000),
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
