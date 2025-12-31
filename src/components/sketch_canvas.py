"""Sketch Canvas component wrapper for NiceGUI.

Provides a freehand drawing canvas using Fabric.js integrated as a Vue component.
"""

import base64
import logging
from pathlib import Path
from typing import Callable, Optional

from nicegui.element import Element

logger = logging.getLogger(__name__)


class SketchCanvas(Element, component="sketch_canvas.vue"):
    """A freehand drawing canvas component.

    Uses Fabric.js for canvas drawing with brush, eraser, and export functionality.
    """

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        background_color: str = "#ffffff",
        on_save: Optional[Callable[[str], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
    ):
        """Initialize the sketch canvas.

        Args:
            width: Canvas width in pixels.
            height: Canvas height in pixels.
            background_color: Background color (hex string).
            on_save: Callback function when save button is clicked, receives base64 data URL.
            on_ready: Callback when the component is mounted and ready.
        """
        super().__init__()
        self._props["width"] = width
        self._props["height"] = height
        self._props["backgroundColor"] = background_color

        if on_save:
            self.on("save", lambda e: on_save(e.args))
        if on_ready:
            self.on("ready", lambda _: on_ready())

    def clear(self) -> None:
        """Clear the canvas."""
        self.run_method("clearCanvas")

    def get_image_data(self) -> str:
        """Get the current canvas content as a base64 PNG data URL.

        Note: This is an async operation, use with await.
        """
        return self.run_method("getImageData")

    def load_image(self, data_url: str) -> None:
        """Load an image onto the canvas.

        Args:
            data_url: Base64 data URL of the image to load.
        """
        self.run_method("loadImage", data_url)


def save_sketch_to_file(data_url: str | dict, output_path: Path) -> Path:
    """Save a base64 data URL sketch to a PNG file.

    Args:
        data_url: Base64 data URL (e.g., "data:image/png;base64,...")
                  Can also be a dict containing the data URL (from NiceGUI event args).
        output_path: Path where to save the PNG file.

    Returns:
        The path to the saved file.

    Raises:
        TypeError: If data_url is not a string or extractable from the input.
    """
    # Handle case where data_url comes from NiceGUI event args as a dict
    if isinstance(data_url, dict):
        # Try common keys that might contain the data URL
        # 'detail' is used by browser CustomEvent objects
        for key in ["detail", "dataUrl", "data_url", "url", "data", "args"]:
            if key in data_url and isinstance(data_url[key], str):
                data_url = data_url[key]
                break
        else:
            # If it's a dict but we couldn't find a string value, check for first string value
            for value in data_url.values():
                if isinstance(value, str) and (
                    value.startswith("data:") or len(value) > 100
                ):
                    data_url = value
                    break
            else:
                raise TypeError(
                    f"Expected data_url to be a string or dict containing a data URL, "
                    f"got dict with keys: {list(data_url.keys())}"
                )

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

    logger.info(f"Saved sketch to {output_path}")
    return output_path
