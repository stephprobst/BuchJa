import logging
from datetime import datetime
from nicegui import ui
from src.app import APP
from src._utils import notify_error
from src.components.sketch_canvas import SketchCanvas, save_sketch_to_file

logger = logging.getLogger(__name__)


def build_sketch_tab():
    """Build the Sketch tab content."""
    with ui.column().classes("w-full gap-6 p-4"):
        with ui.card().classes("w-full"):
            ui.label("Sketching Canvas").classes("text-lg font-bold")
            ui.label(
                "Draw a rough sketch to use as a reference for generation. Aspect ratio of the sketch canvas matches the aspect ratio of the book settings."
            ).classes("text-gray-600 text-sm mb-4")

            with ui.row().classes("w-full items-center gap-4 mb-4"):
                filename_input = ui.input(
                    "Sketch Name", value="my_sketch", placeholder="Enter filename"
                ).classes("w-64")

                ui.label('Sketches are saved to the "References" folder.').classes(
                    "text-gray-500 text-sm italic"
                )

            async def save_sketch(data_url: str):
                if not APP.settings or not APP.settings.working_folder:
                    notify_error("Please configure settings first!")
                    return

                if not data_url:
                    return

                try:
                    # Save to references folder
                    refs_folder = APP.settings.working_folder / "references"
                    refs_folder.mkdir(parents=True, exist_ok=True)

                    name = filename_input.value or "sketch"
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{name}_{timestamp}.png"
                    file_path = refs_folder / filename

                    save_sketch_to_file(data_url, file_path)

                    # No need to call add_image as we saved directly to the folder
                    # and add_image would create a duplicate

                    ui.notify(f"Sketch saved: {filename}", type="positive")

                    # Refresh other tabs if needed
                    APP.trigger_refresh()

                except Exception as e:
                    logger.exception("Failed to save sketch")
                    notify_error(f"Failed to save sketch: {e}", e)

            @ui.refreshable
            def render_canvas():
                width, height = 800, 600
                if APP.settings:
                    try:
                        ratio_str = APP.settings.aspect_ratio
                        w_ratio, h_ratio = map(int, ratio_str.split(":"))

                        # Calculate dimensions fitting in 800x600 box (or similar)
                        # We'll use a max dimension of 800 for width or height
                        max_dim = 800
                        if w_ratio >= h_ratio:
                            width = max_dim
                            height = int(max_dim * (h_ratio / w_ratio))
                        else:
                            height = max_dim
                            width = int(max_dim * (w_ratio / h_ratio))
                    except Exception:
                        pass

                SketchCanvas(
                    width=width,
                    height=height,
                    on_save=save_sketch,
                    background_color="#ffffff",
                )

            render_canvas()
            APP.register_refresh_callback(render_canvas.refresh)
