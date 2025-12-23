import logging
import asyncio
import platform
import subprocess
from pathlib import Path
from nicegui import ui
from src.app import APP
from src._utils import notify_error

logger = logging.getLogger(__name__)


def build_export_tab():
    """Build the Export tab content for creating PDFs."""
    with ui.column().classes("w-full gap-6 p-4"):
        with ui.card().classes("w-full"):
            ui.label("Export to PDF").classes("text-lg font-bold")
            ui.label(
                "Compile all ordered pages into a PDF document ready for printing."
            ).classes("text-gray-600 text-sm mb-4")

            filename_input = ui.input(
                "Output Filename",
                value="my_book",
                placeholder="Enter filename (without .pdf)",
            ).classes("w-64")
            filename_input._props["marker"] = "export-filename-input"

            async def export_pdf():
                if not APP.settings or not APP.settings.working_folder:
                    notify_error("Please configure settings first!")
                    return

                if not APP.project_manager:
                    notify_error("No project data found!")
                    return

                pages = APP.project_manager.get_ordered_pages()
                if not pages:
                    ui.notify("No pages to export!", type="warning")
                    return

                from src.services.pdf_service import PdfService

                pdf_service = PdfService()
                # Save exports to root working folder
                export_folder = APP.settings.working_folder

                if export_folder:
                    output_path = export_folder / f"{filename_input.value}.pdf"

                    try:
                        page_paths: list[Path] = []
                        for p in pages:
                            raw_path = p.get("path")
                            if not raw_path:
                                continue
                            page_path = Path(raw_path)
                            if (
                                not page_path.is_absolute()
                                and APP.settings
                                and APP.settings.working_folder
                            ):
                                page_path = APP.settings.working_folder / page_path
                            page_paths.append(page_path)

                        if APP.status_footer:
                            async with APP.status_footer.busy("Exporting PDF..."):
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(
                                    None,
                                    lambda: pdf_service.create_pdf(
                                        page_paths,
                                        output_path,
                                        APP.settings.aspect_ratio,
                                    ),
                                )
                        else:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda: pdf_service.create_pdf(
                                    page_paths,
                                    output_path,
                                    APP.settings.aspect_ratio,
                                ),
                            )
                        ui.notify(f"PDF exported: {output_path}", type="positive")
                    except Exception as e:
                        logger.exception("PDF export failed")
                        notify_error(f"Export failed: {e}", e)

            def open_export_folder():
                if not APP.settings:
                    ui.notify("Settings not initialized", type="warning")
                    return

                folder = APP.settings.working_folder
                if not folder:
                    ui.notify("Working folder not configured", type="warning")
                    return

                if not folder.exists():
                    ui.notify(f"Folder does not exist: {folder}", type="warning")
                    return

                try:
                    if platform.system() == "Windows":
                        # Use explorer to open folder, which handles bringing to front/new window better
                        subprocess.Popen(["explorer", str(folder)])
                    elif platform.system() == "Darwin":
                        subprocess.Popen(["open", str(folder)])
                    else:
                        subprocess.Popen(["xdg-open", str(folder)])
                except Exception as e:
                    logger.error(f"Failed to open folder {folder}: {e}")
                    ui.notify(f"Could not open folder: {e}", type="negative")

            with ui.row().classes("gap-2"):
                export_btn = ui.button(
                    "Export PDF", on_click=export_pdf, icon="download"
                ).props("color=primary")
                export_btn._props["marker"] = "export-pdf-btn"

                ui.button(
                    "OPEN EXPORT FOLDER IN FILE EXPLORER",
                    on_click=open_export_folder,
                    icon="folder_open",
                ).props("outline")
