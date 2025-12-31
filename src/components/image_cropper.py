"""Image Cropper component wrapper for NiceGUI.

Provides an image cropping interface using Cropper.js integrated as a Vue component.
"""

import base64
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import Request
from nicegui import app, background_tasks, Client
from nicegui.element import Element

logger = logging.getLogger(__name__)


@dataclass
class _CropCallbackInfo:
    """Stores callback and client context for crop operations."""

    callback: Callable[[str], None]
    client: Client


# Store for pending crop callbacks, keyed by upload_id
_crop_callbacks: dict[str, _CropCallbackInfo] = {}


@app.post("/api/crop-upload/{upload_id}")
async def crop_upload_endpoint(upload_id: str, request: Request):
    """Receive cropped image data via HTTP POST to bypass websocket size limits."""
    try:
        body = await request.body()
        data_url = body.decode("utf-8")

        if upload_id in _crop_callbacks:
            # Don't pop - keep the callback registered for reuse
            info = _crop_callbacks[upload_id]

            # Run the callback in the correct client context
            async def run_callback():
                with info.client:
                    info.callback(data_url)

            background_tasks.create(run_callback())
            return {"status": "ok"}
        else:
            logger.warning(f"No callback found for upload_id: {upload_id}")
            return {"status": "error", "message": "No callback registered"}
    except Exception as e:
        logger.error(f"Error processing crop upload: {e}")
        return {"status": "error", "message": str(e)}


class ImageCropper(Element, component="image_cropper.vue"):
    """An image cropping component.

    Uses Cropper.js for image cropping with rotation, flipping, and aspect ratio control.
    """

    def __init__(
        self,
        initial_aspect_ratio: str = "free",
        on_crop: Optional[Callable[[str | dict], None]] = None,
        on_error: Optional[Callable[[str | dict], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
    ):
        """Initialize the image cropper.

        Args:
            initial_aspect_ratio: Initial aspect ratio ('free', '1:1', '3:4', '4:3', '9:16', '16:9').
            on_crop: Callback when crop button is clicked, receives base64 data URL.
            on_error: Callback when an error occurs, receives error message.
            on_ready: Callback when the component is mounted and ready.
        """
        super().__init__()
        self._props["initialAspectRatio"] = initial_aspect_ratio

        # Generate a unique upload ID for this cropper instance
        self._upload_id = str(uuid.uuid4())
        self._props["uploadId"] = self._upload_id

        # Register the crop callback for HTTP upload with client context
        if on_crop:
            _crop_callbacks[self._upload_id] = _CropCallbackInfo(
                callback=on_crop,
                client=self.client,
            )

        def _unwrap_nicegui_event_args(args: Any) -> Any:
            # NiceGUI forwards Vue emits via a browser CustomEvent.
            # Depending on the bridge, `detail` may be the payload itself, or a list of emitted args.
            if isinstance(args, dict) and "detail" in args:
                detail = args.get("detail")
                if isinstance(detail, (list, tuple)):
                    return detail[0] if detail else None
                return detail
            return args

        if on_error:
            self.on("error", lambda e: on_error(_unwrap_nicegui_event_args(e.args)))
        if on_ready:
            self.on("ready", lambda _: on_ready())

    def _handle_unmount(self):
        """Clean up callback when component is unmounted."""
        if self._upload_id in _crop_callbacks:
            del _crop_callbacks[self._upload_id]
        if hasattr(super(), "_handle_unmount"):
            super()._handle_unmount()

    def load_image(self, src: str) -> None:
        """Load an image into the cropper.

        Args:
            src: Image source URL or base64 data URL.
        """
        self.run_method("loadImage", src)

    def set_aspect_ratio(self, ratio: str) -> None:
        """Set the crop aspect ratio.

        Args:
            ratio: Aspect ratio string ('free', '1:1', '3:4', etc.)
        """
        self.run_method("setAspectRatio", ratio)

    def get_cropped_image(self) -> str:
        """Get the cropped image as a base64 PNG data URL.

        Note: This is an async operation, use with await.
        """
        return self.run_method("getCroppedImage")

    def clear(self) -> None:
        """Clear the cropper and remove the image."""
        self.run_method("clear")


def save_cropped_image(data_url: str | dict, output_path: Path) -> Path:
    """Save a base64 data URL cropped image to a PNG file.

    Args:
        data_url: Base64 data URL (e.g., "data:image/png;base64,...")
                  Can also be a dict containing the data URL (from NiceGUI event args).
        output_path: Path where to save the PNG file.

    Returns:
        The path to the saved file.

    Raises:
        TypeError: If data_url is not a string or extractable from the input.
    """

    def _looks_like_data_url(value: str) -> bool:
        return value.startswith("data:") or len(value) > 100

    def _extract_data_url(value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value if _looks_like_data_url(value) else None

        if isinstance(value, dict):
            # 'detail' is used by browser CustomEvent objects; can be payload or list of emitted args.
            if "detail" in value:
                extracted = _extract_data_url(value.get("detail"))
                if extracted is not None:
                    return extracted

            for key in ["dataUrl", "data_url", "url", "data", "args"]:
                extracted = _extract_data_url(value.get(key))
                if extracted is not None:
                    return extracted

            # Fallback: scan values (handles nested dicts)
            for child in value.values():
                extracted = _extract_data_url(child)
                if extracted is not None:
                    return extracted
            return None

        if isinstance(value, (list, tuple)):
            for child in value:
                extracted = _extract_data_url(child)
                if extracted is not None:
                    return extracted
            return None

        return None

    # Handle case where data_url comes from NiceGUI event args as a dict
    if isinstance(data_url, dict):
        extracted = _extract_data_url(data_url)
        if extracted is None:
            raise TypeError(
                f"Expected data_url to be a string or dict containing a data URL, "
                f"got dict with keys: {list(data_url.keys())}"
            )
        data_url = extracted

    if not isinstance(data_url, str):
        raise TypeError(
            f"Expected data_url to be a string, got {type(data_url).__name__}"
        )

    # Extract base64 data from data URL
    if "," in data_url:
        _, base64_data = data_url.split(",", 1)
    else:
        base64_data = data_url

    # Decode and save
    image_data = base64.b64decode(base64_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(image_data)

    logger.info(f"Saved cropped image to {output_path}")
    return output_path


def image_to_data_url(image_path: Path) -> str:
    """Convert an image file to a base64 data URL.

    Args:
        image_path: Path to the image file.

    Returns:
        Base64 data URL string.
    """
    import mimetypes

    mime_type, _ = mimetypes.guess_type(str(image_path))
    if mime_type is None:
        mime_type = "image/png"

    with open(image_path, "rb") as f:
        image_data = f.read()

    base64_data = base64.b64encode(image_data).decode("utf-8")
    return f"data:{mime_type};base64,{base64_data}"
