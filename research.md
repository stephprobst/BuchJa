# Research Findings

## Task Overview
Enable keyboard navigation (left/right arrows) in the fullscreen image view of the Image Manager.

## Relevant Files
- `src/components/image_manager.py`: Contains the `ImageManager` class and `_show_image_dialog` method responsible for the fullscreen view.

## Key Components
- `ImageManager`: Main component class.
- `_show_image_dialog`: Method that creates and opens the fullscreen dialog.
- `_build_image_card`: Method that creates thumbnails and the "view" button.

## Findings
- Currently, `_show_image_dialog` creates a new `ui.dialog` instance every time it is called.
- It only accepts a single image path and name, unaware of the surrounding list of images.
- To implement navigation, the dialog needs context (list of images and current index).
- To handle keyboard events, `ui.keyboard` can be used.
- To avoid memory leaks and multiple event listeners, it is better to refactor the dialog to be a persistent component instance (created once, reused) rather than creating a new one on every click.

## Plan
1.  Refactor `ImageManager` to maintain a single `_preview_dialog` instance.
2.  Add state for the preview (current images list, current index).
3.  Implement `_create_preview_dialog` to build the UI and bind keyboard events.
4.  Update `_build_image_card` to pass the necessary context (list and index) when opening the preview.
