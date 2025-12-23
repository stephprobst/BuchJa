import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from nicegui import ui
from src.app import APP
from src._utils import notify_error, check_folder_changes
from src.components.image_cropper import (
    ImageCropper,
    save_cropped_image,
    image_to_data_url,
)

logger = logging.getLogger(__name__)


def build_crop_tab():
    """Build the Crop tab content for cropping elements from existing images."""
    with ui.column().classes("w-full gap-6 p-4"):
        # Crop from Existing Section
        with ui.card().classes("w-full"):
            ui.label("Crop from Existing Image").classes("text-lg font-bold")
            ui.label(
                "Select an existing image and crop a portion to create a new reference image."
            ).classes("text-gray-600 text-sm mb-4")

            # Image selection grid
            crop_source_container = ui.element("div").classes("w-full")
            cropper_container = ui.element("div").classes("w-full mt-4")
            cropper_instance: list[Optional[ImageCropper]] = [None]
            selected_source_path: list[Optional[Path]] = [None]

            def build_crop_source_grid():
                crop_source_container.clear()
                with crop_source_container:
                    if not APP.project_manager or not APP.settings:
                        ui.label("Please configure settings first.").classes(
                            "text-gray-500 text-sm"
                        )
                        return

                    # Get all images from all categories
                    all_images = []
                    for category in ["inputs", "references", "pages"]:
                        images = APP.project_manager.get_images(category)
                        for img in images:
                            img["_category"] = category
                            all_images.append(img)

                    if not all_images:
                        ui.label(
                            "No images available. Upload some images first."
                        ).classes("text-gray-500 text-sm")
                        return

                    ui.label("Select an image to crop:").classes(
                        "text-sm font-medium mb-2"
                    )

                    with ui.element("div").classes("grid grid-cols-6 gap-2"):
                        for img in all_images:
                            img_path = img.get("path")
                            img_name = img.get(
                                "name", Path(img_path).stem if img_path else "Unknown"
                            )

                            if img_path:
                                full_path = Path(img_path)
                                if not full_path.is_absolute():
                                    full_path = APP.settings.working_folder / img_path

                                thumb_path = None
                                if APP.image_service:
                                    try:
                                        thumb_path = APP.image_service.ensure_thumbnail(
                                            full_path
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to ensure thumbnail for {full_path}: {e}"
                                        )

                                if not thumb_path:
                                    thumb_path = (
                                        APP.settings.working_folder
                                        / ".thumbnails"
                                        / f"{full_path.stem}_thumb.png"
                                    )

                                display_path = (
                                    thumb_path if thumb_path.exists() else full_path
                                )

                                if display_path.exists():
                                    with ui.card().classes(
                                        "cursor-pointer p-1 hover:shadow-md transition-shadow"
                                    ) as card:
                                        with ui.element("div").classes(
                                            "w-full h-16 bg-gray-100 flex items-center justify-center rounded"
                                        ):
                                            ui.image(str(display_path)).props(
                                                "fit=contain"
                                            ).classes("w-full h-full")
                                        ui.label(img_name[:12]).classes(
                                            "text-xs truncate text-center"
                                        )

                                        def select_for_crop(card=card, path=full_path):
                                            selected_source_path[0] = path
                                            load_image_for_cropping(path)

                                        card.on("click", select_for_crop)

            def load_image_for_cropping(image_path: Path):
                cropper_container.clear()
                with cropper_container:
                    ui.label(f"Cropping: {image_path.name}").classes(
                        "text-sm font-medium mb-2"
                    )

                    def on_crop(data_url: str):
                        if not APP.settings or not APP.settings.working_folder:
                            notify_error("Working folder not configured!")
                            return

                        # Save crops to references folder by default
                        ref_folder = APP.settings.get_subfolder("references")
                        if ref_folder:
                            timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                            crop_filename = f"crop_{timestamp}.png"
                            crop_path = ref_folder / crop_filename
                            save_cropped_image(data_url, crop_path)

                            # if APP.project_manager:
                            #     APP.project_manager.add_image(crop_path, 'references', crop_path.stem)

                            ui.notify(
                                f"Cropped image saved to references: {crop_filename}",
                                type="positive",
                            )
                            check_folder_changes()
                            build_crop_source_grid()  # Refresh to show new image

                    def on_error(error_msg: str):
                        notify_error(f"Crop error: {error_msg}")

                    cropper = ImageCropper(
                        initial_aspect_ratio="free",
                        on_crop=on_crop,
                        on_error=on_error,
                    )
                    cropper_instance[0] = cropper

                    # Load the image into cropper
                    data_url = image_to_data_url(image_path)
                    ui.timer(0.5, lambda: cropper.load_image(data_url), once=True)

            # Initial build
            build_crop_source_grid()

            ui.button("↻ Refresh Images", on_click=build_crop_source_grid).props(
                "flat dense"
            ).classes("mt-2")

    # Register refresh callbacks
    APP.register_refresh_callback(build_crop_source_grid)
