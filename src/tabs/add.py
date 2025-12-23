from nicegui import ui
from src.app import APP
from src._utils import check_folder_changes, notify_error


def build_add_tab():
    """Build the Add tab content for uploading images."""
    with ui.column().classes("w-full gap-6 p-4"):
        # Upload Section
        with ui.card().classes("w-full"):
            ui.label("Upload Reference Images").classes("text-lg font-bold")
            ui.label(
                "Upload photos or reference images to use for character creation and scene generation."
            ).classes("text-gray-600 text-sm mb-4")

            async def handle_upload(e):
                if not APP.settings or not APP.settings.working_folder:
                    notify_error("Please set a working folder first!")
                    return

                input_folder = APP.settings.get_subfolder("inputs")
                if input_folder:
                    file_path = input_folder / e.file.name
                    await e.file.save(file_path)
                    ui.notify(f"Uploaded: {e.file.name}", type="positive")

                    if APP.project_manager:
                        # APP.project_manager.add_image(file_path, 'inputs', file_path.stem)
                        pass

                    check_folder_changes()

            ui.upload(
                label="Drop images here or click to upload",
                on_upload=handle_upload,
                multiple=True,
                auto_upload=True,
            ).classes("w-full").props('accept="image/*"')

            ui.label(
                'Tip: You can also copy images directly into the "inputs" folder in your working directory.'
            ).classes("text-gray-500 text-xs mt-2")
