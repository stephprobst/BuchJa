"""BuchJa - Main Application Entry Point."""

import logging
import asyncio
import socket
from nicegui import ui
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

# Set window icon (browser tab icon)
logo_path = Path(__file__).parent / "materials" / "logo.png"
if not logo_path.exists():
    raise FileNotFoundError(f"Icon file not found: {logo_path}")


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

            ui.separator().props("vertical").classes("mx-2")

            # Shutdown Dialog
            with ui.dialog() as shutdown_dialog, ui.card().classes("w-80"):
                with ui.column().classes("w-full items-center text-center gap-4"):
                    ui.icon("check_circle", color="positive").classes("text-6xl")
                    ui.label("Shutdown Complete").classes("text-h6")
                    ui.label(
                        "The application has been stopped.\nYou can now close this browser tab."
                    ).classes("text-gray-600")

            async def shutdown_app():
                shutdown_dialog.open()
                shutdown_dialog.props("persistent")
                await asyncio.sleep(0.5)
                APP.shutdown()

            # Shutdown button
            ui.button(icon="power_settings_new", on_click=shutdown_app).props(
                "flat round dense color=white"
            ).tooltip("Shutdown Application")

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


def _find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def main():
    """Application entry point."""

    # Dynamic Port Selection to prevent conflicts
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    print(
        r"""
 ____             _          _       _ 
|  _ \           | |        | |     | |
| |_) |_   _  ___| |__      | | __ _| |
|  _ <| | | |/ __| '_ \ _   | |/ _` | |
| |_) | |_| | (__| | | | |__| | (_| |_|
|____/ \__,_|\___|_| |_|\____/ \__,_(_)
                                       
    """
    )
    print("Buch gut! Ja! Buch sehr gut! \n")

    print("#" * 50)
    print(" CLICK HERE TO OPEN APP IN YOUR BROWSER:")
    print(f" {url}")
    print("#" * 50)
    print(" CLOSING THIS WINDOW WILL SHUT DOWN THE APP.")
    print("#" * 50)
    print("\n")

    ui.run(
        title="BuchJa",
        native=False,
        reload=False,
        favicon=logo_path,
        show=True,
        host="127.0.0.1",
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
