"""Image Manager component for Book Creator.

Provides UI for managing project images including:
- Grid display with thumbnails
- Drag-and-drop reordering
- Category assignment (pages, characters, references)
- Filesystem-based persistence
"""

import logging
import shutil
import re
import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

logger = logging.getLogger(__name__)

class ProjectManager:
    """Manages project images using filesystem structure."""
    
    def __init__(self, working_folder: Path):
        """Initialize project manager.
        
        Args:
            working_folder: Path to the project working folder.
        """
        self._working_folder = working_folder
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required directories exist."""
        for category in ['pages', 'references', 'inputs']:
            (self._working_folder / category).mkdir(parents=True, exist_ok=True)
        (self._working_folder / ".thumbnails").mkdir(parents=True, exist_ok=True)

    def sync_with_filesystem(self) -> None:
        """No-op as we now read directly from filesystem."""
        pass

    def get_images(self, category: str) -> list[dict]:
        """Get all images in a category from filesystem."""
        folder = self._working_folder / category
        if not folder.exists():
            return []
        
        images = []
        extensions = {'.png', '.jpg', '.jpeg', '.webp'}
        
        try:
            files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in extensions]
        except OSError:
            return []
        
        # Sort files. For pages, we rely on filename order.
        files.sort(key=lambda f: f.name)
        
        for i, f in enumerate(files):
            rel_path = f.relative_to(self._working_folder)
            # Use forward slashes for consistency
            rel_path_str = str(rel_path).replace('\\', '/')
            
            name = f.stem
            if category == 'pages':
                match = re.match(r'^\d{3}_(.*)', name)
                if match:
                    name = match.group(1)
            
            images.append({
                'id': rel_path_str,
                'path': rel_path_str,
                'category': category,
                'name': name,
                'order': i + 1 if category == 'pages' else 0
            })
        return images

    def get_ordered_pages(self) -> list[dict]:
        """Get pages sorted by order (filename)."""
        return self.get_images('pages')

    def get_all_images(self) -> dict:
        """Get all images organized by category."""
        return {
            'pages': self.get_images('pages'),
            'inputs': self.get_images('inputs'),
            'references': self.get_images('references'),
        }

    def add_image(self, path: Path, category: str, name: str = "") -> dict:
        """Add an image to the project by copying it to the category folder."""
        target_folder = self._working_folder / category
        target_folder.mkdir(parents=True, exist_ok=True)
        
        target_name = name if name else path.name
        if not Path(target_name).suffix:
            target_name += path.suffix
            
        # Handle ordering for pages
        if category == 'pages':
            existing = self.get_images('pages')
            next_order = len(existing) + 1
            # Ensure name has prefix if not present
            if not re.match(r'^\d{3}_', target_name):
                target_name = f"{next_order:03d}_{target_name}"
        
        target_path = target_folder / target_name
        
        # Handle duplicates
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_folder / f"{stem}_{counter}{suffix}"
                counter += 1
        
        shutil.copy2(path, target_path)
        logger.info(f"Added image to {category}: {target_path}")
        
        rel_path = target_path.relative_to(self._working_folder)
        rel_path_str = str(rel_path).replace('\\', '/')
        
        return {
            'id': rel_path_str,
            'path': rel_path_str,
            'category': category,
            'name': target_path.stem,
            'order': 0
        }

    def remove_image(self, image_id: str) -> bool:
        """Remove an image from the project by ID (relative path)."""
        try:
            file_path = self._working_folder / image_id
            if file_path.exists():
                # Delete thumbnail first
                thumb_path = self._working_folder / ".thumbnails" / f"{file_path.stem}_thumb.png"
                if thumb_path.exists():
                    thumb_path.unlink()
                
                file_path.unlink()
                logger.info(f"Removed image: {image_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to remove image {image_id}: {e}")
        return False

    def move_image(self, image_id: str, new_category: str) -> bool:
        """Move an image to a different category folder."""
        source_path = self._working_folder / image_id
        if not source_path.exists():
            return False
            
        target_folder = self._working_folder / new_category
        target_folder.mkdir(parents=True, exist_ok=True)
        
        # Determine target name
        filename = source_path.name
        
        # Strip prefix if moving FROM pages or TO pages (to re-add correctly)
        clean_name = filename
        match = re.match(r'^\d{3}_(.*)', filename)
        if match:
            clean_name = match.group(1)
            
        if new_category == 'pages':
            existing = self.get_images('pages')
            next_order = len(existing) + 1
            target_name = f"{next_order:03d}_{clean_name}"
        else:
            target_name = clean_name
            
        target_path = target_folder / target_name
        
        # Handle collision
        if target_path.exists():
             stem = target_path.stem
             suffix = target_path.suffix
             counter = 1
             while target_path.exists():
                 target_path = target_folder / f"{stem}_{counter}{suffix}"
                 counter += 1
        
        try:
            # Move file
            shutil.move(str(source_path), str(target_path))
            
            # Move/Rename thumbnail
            src_thumb = self._working_folder / ".thumbnails" / f"{source_path.stem}_thumb.png"
            if src_thumb.exists():
                dst_thumb = self._working_folder / ".thumbnails" / f"{target_path.stem}_thumb.png"
                shutil.move(str(src_thumb), str(dst_thumb))
                
            logger.info(f"Moved image {image_id} to {new_category}")
            return True
        except Exception as e:
            logger.error(f"Failed to move image {image_id}: {e}")
            return False

    def update_page_order(self, page_ids: list[str]) -> None:
        """Update the order of pages by renaming files with prefixes."""
        pages_folder = self._working_folder / 'pages'
        if not pages_folder.exists():
            return

        moves = []
        for i, pid in enumerate(page_ids):
            # pid is relative path "pages/filename"
            current_path = self._working_folder / pid
            if not current_path.exists():
                continue
                
            filename = current_path.name
            clean_name = filename
            match = re.match(r'^\d{3}_(.*)', filename)
            if match:
                clean_name = match.group(1)
            
            temp_name = f"__temp_{i:04d}__{clean_name}"
            temp_path = pages_folder / temp_name
            moves.append((current_path, temp_path, clean_name))

        # Rename to temp
        temp_moves = []
        for current_path, temp_path, clean_name in moves:
            self._rename_file_and_thumb(current_path, temp_path)
            temp_moves.append((temp_path, clean_name))
            
        # Rename to final
        for i, (temp_path, clean_name) in enumerate(temp_moves):
            final_name = f"{i+1:03d}_{clean_name}"
            final_path = pages_folder / final_name
            self._rename_file_and_thumb(temp_path, final_path)
            
        logger.info("Updated page order")

    def rename_image(self, image_id: str, new_name: str) -> bool:
        """Rename an image."""
        source_path = self._working_folder / image_id
        if not source_path.exists():
            return False
            
        category = source_path.parent.name
        
        # Construct new filename
        if category == 'pages':
            # Keep the prefix
            match = re.match(r'^(\d{3}_)(.*)', source_path.name)
            if match:
                prefix = match.group(1)
                target_name = f"{prefix}{new_name}{source_path.suffix}"
            else:
                # Should not happen for pages, but fallback
                target_name = f"{new_name}{source_path.suffix}"
        else:
            target_name = f"{new_name}{source_path.suffix}"
            
        target_path = source_path.parent / target_name
        
        if target_path.exists() and target_path != source_path:
            logger.warning(f"Target {target_path} already exists")
            return False
            
        try:
            self._rename_file_and_thumb(source_path, target_path)
            logger.info(f"Renamed {image_id} to {target_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename {image_id}: {e}")
            return False

    def _rename_file_and_thumb(self, src: Path, dst: Path):
        try:
            # Rename thumbnail first (using src stem)
            src_thumb = self._working_folder / ".thumbnails" / f"{src.stem}_thumb.png"
            if src_thumb.exists():
                dst_thumb = self._working_folder / ".thumbnails" / f"{dst.stem}_thumb.png"
                src_thumb.rename(dst_thumb)
            
            src.rename(dst)
        except Exception as e:
            logger.error(f"Failed to rename {src} to {dst}: {e}")


class ImageManager:
    """NiceGUI component for managing project images."""
    
    def __init__(
        self,
        project_manager: ProjectManager,
        working_folder: Path,
        on_select: Optional[Callable[[str], None]] = None,
        image_service = None,
    ):
        """Initialize the image manager UI.
        
        Args:
            project_manager: ProjectManager instance.
            working_folder: Path to working folder.
            on_select: Callback when an image is selected.
            image_service: Optional ImageService instance for thumbnail generation.
        """
        self._project = project_manager
        self._working_folder = working_folder
        self._on_select = on_select
        self._image_service = image_service
        self._selected_ids: set[str] = set()
        self._container = None
        self._current_tab = 'Pages'
        
        # Preview dialog state
        self._preview_dialog = None
        self._preview_image = None
        self._preview_label = None
        self._preview_images: list[dict] = []
        self._preview_index: int = 0
        
        with ui.column().classes('w-full gap-4') as self._container:
            self._build_ui()

    def _get_thumbnail_path(self, image_path: str) -> Path:
        """Get thumbnail path for an image."""
        path = Path(image_path)
        if not path.is_absolute():
            path = self._working_folder / path
        
        # Try to ensure thumbnail exists if service is available
        if self._image_service:
            try:
                thumb = self._image_service.ensure_thumbnail(path)
                if thumb and thumb.exists():
                    return thumb
            except Exception as e:
                logger.warning(f"Failed to ensure thumbnail for {path}: {e}")
        
        thumb_path = self._working_folder / ".thumbnails" / f"{path.stem}_thumb.png"
        
        # Return thumbnail if exists, otherwise original
        if thumb_path.exists():
            return thumb_path
        return path

    def _open_folder(self, category: str) -> None:
        """Open the category folder in the system file explorer."""
        folder = self._working_folder / category
        folder.mkdir(parents=True, exist_ok=True)
        
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
            ui.notify(f"Could not open folder: {e}", type='negative')

    def _build_ui(self) -> None:
        """Build the image manager UI."""
        # Category tabs
        with ui.tabs(value=self._current_tab).classes('w-full').bind_value(self, '_current_tab') as tabs:
            ui.tab('Pages')
            ui.tab('References')
            ui.tab('Inputs')
        
        with ui.tab_panels(tabs, value=self._current_tab).classes('w-full'):
            with ui.tab_panel('Pages'):
                self._build_pages_grid()
            
            with ui.tab_panel('References'):
                self._build_category_grid('references')
            
            with ui.tab_panel('Inputs'):
                self._build_category_grid('inputs')

    def _move_page(self, index: int, direction: int) -> None:
        """Move page at index by direction (-1 for left, 1 for right)."""
        pages = self._project.get_ordered_pages()
        if not pages:
            return
            
        new_index = index + direction
        if 0 <= new_index < len(pages):
            # Swap
            pages[index], pages[new_index] = pages[new_index], pages[index]
            page_ids = [p['id'] for p in pages]
            self._project.update_page_order(page_ids)
            self.refresh()

    def open_current_folder(self) -> None:
        """Open the currently selected category folder."""
        self._open_folder(self._current_tab.lower())

    def _build_pages_grid(self) -> None:
        """Build the pages grid with drag-drop reordering."""
        pages = self._project.get_ordered_pages()
        
        if not pages:
            ui.label('No pages yet. Generate some pages first!').classes('text-gray-500')
            return
        
        # Build sortable grid
        page_ids = [p['id'] for p in pages]
        
        with ui.element('div').classes('grid grid-cols-4 gap-4') as grid:
            for i, page in enumerate(pages):
                self._build_image_card(page, 'pages', index=i, total=len(pages))

    def _build_category_grid(self, category: str) -> None:
        """Build a grid for a category."""
        images = self._project.get_images(category)
        
        if not images:
            ui.label(f'No {category} yet.').classes('text-gray-500')
            return
        
        with ui.element('div').classes('grid grid-cols-4 gap-4'):
            for img in images:
                self._build_image_card(img, category)

    def _show_rename_dialog(self, image_id: str, current_name: str) -> None:
        """Show dialog to rename image."""
        with ui.dialog() as dialog, ui.card():
            ui.label('Rename Image').classes('text-lg font-bold')
            name_input = ui.input('New Name', value=current_name).classes('w-full')
            
            def save():
                new_name = name_input.value.strip()
                if new_name and new_name != current_name:
                    if self._project.rename_image(image_id, new_name):
                        ui.notify('Image renamed')
                        dialog.close()
                        self.refresh()
                    else:
                        ui.notify('Failed to rename (name might exist)', type='negative')
                else:
                    dialog.close()
            
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', on_click=save).props('flat')
        
        dialog.open()

    def _build_image_card(self, image_data: dict, category: str, index: int = -1, total: int = 0) -> None:
        """Build an image card with thumbnail and controls."""
        image_id = image_data['id']
        image_path = image_data['path']
        image_name = image_data.get('name', Path(image_path).stem)
        
        thumb_path = self._working_folder / ".thumbnails" / f"{Path(image_path).stem}_thumb.png"
        
        with ui.card().classes('cursor-pointer hover:shadow-lg transition-shadow'):
            # Thumbnail with letterboxing (gray background, image fully visible)
            with ui.element('div').classes('w-full h-32 bg-gray-100 flex items-center justify-center'):
                if thumb_path.exists():
                    ui.image(str(thumb_path)).props('fit=contain').classes('w-full h-full')
                else:
                    ui.icon('image', size='xl').classes('text-gray-400')
            
            # Line 1: Name
            with ui.row().classes('w-full justify-center px-2 pt-2'):
                ui.label(image_name).classes('text-sm truncate w-full text-center').tooltip(image_name)

            # Line 2: Navigation (Pages only)
            if category == 'pages':
                with ui.row().classes('w-full items-center justify-center gap-2 px-2'):
                    if total > 1:
                        if index > 0:
                            ui.button(icon='arrow_back', on_click=lambda: self._move_page(index, -1)).props('flat dense round size=sm')
                        else:
                            ui.button(icon='arrow_back').props('flat dense round size=sm disabled')
                    
                    order = image_data.get('order', 0)
                    ui.badge(str(order)).props('color=primary')
                    
                    if total > 1:
                        if index < total - 1:
                            ui.button(icon='arrow_forward', on_click=lambda: self._move_page(index, 1)).props('flat dense round size=sm')
                        else:
                            ui.button(icon='arrow_forward').props('flat dense round size=sm disabled')

            # Line 3: Actions
            with ui.row().classes('w-full justify-center gap-2 pb-2'):
                # View full size
                def view_image():
                    # Get fresh list to ensure order is correct
                    if category == 'pages':
                        current_images = self._project.get_ordered_pages()
                    else:
                        current_images = self._project.get_images(category)
                    
                    # Find index of current image
                    try:
                        # We match by ID (relative path)
                        current_index = next(i for i, img in enumerate(current_images) if img['id'] == image_id)
                        self._show_image_dialog(current_images, current_index)
                    except StopIteration:
                        ui.notify('Image no longer exists', type='warning')
                
                ui.button(icon='visibility', on_click=view_image).props('flat dense round size=sm').tooltip('View')
                
                # Rename
                def rename(iid=image_id, current_name=image_name):
                    self._show_rename_dialog(iid, current_name)
                
                ui.button(icon='edit', on_click=rename).props('flat dense round size=sm').tooltip('Rename')

                # Move to different category
                with ui.button(icon='drive_file_move').props('flat dense round size=sm').tooltip('Move'):
                    with ui.menu() as menu:
                        for cat in ['pages', 'references', 'inputs']:
                            if cat != category:
                                def move(c=cat, iid=image_id):
                                    self._project.move_image(iid, c)
                                    self.refresh()
                                    ui.notify(f'Moved to {c}')
                                ui.menu_item(f'Move to {cat.title()}', on_click=move)
                
                # Delete
                def delete(iid=image_id):
                    self._project.remove_image(iid)
                    self.refresh()
                    ui.notify('Image removed')
                
                ui.button(icon='delete', on_click=delete).props('flat dense round size=sm color=negative').tooltip('Delete')

    def _create_preview_dialog(self) -> None:
        """Create the persistent preview dialog."""
        with ui.dialog() as self._preview_dialog:
            self._preview_dialog.props('maximized')
            
            def handle_key(e):
                if not self._preview_dialog.value:
                    return
                if not e.action.keydown:
                    return
                    
                if e.key == 'ArrowRight':
                    self._next_preview_image()
                elif e.key == 'ArrowLeft':
                    self._prev_preview_image()
            
            ui.keyboard(on_key=handle_key)
            
            # Container using absolute positioning for reliable fullscreen layout
            with ui.element('div').style(
                'position: absolute; top: 0; left: 0; right: 0; bottom: 0; '
                'display: flex; flex-direction: column; '
                'background-color: #1f2937;'
            ):
                # Header bar - fixed height
                with ui.element('div').style(
                    'height: 48px; width: 100%; '
                    'display: flex; align-items: center; justify-content: space-between; '
                    'padding: 0 16px; background-color: #111827; '
                    'flex-shrink: 0; box-sizing: border-box; z-index: 50;'
                ):
                    self._preview_label = ui.label('').classes('text-lg font-semibold text-white')
                    ui.button(icon='close', on_click=self._preview_dialog.close).props('flat dense color=white')
                
                # Image container - fills remaining space
                with ui.element('div').style(
                    'flex: 1; width: 100%; position: relative; '
                    'display: flex; align-items: center; justify-content: center; '
                    'overflow: hidden; background-color: #000;'
                ):
                    self._preview_image = ui.image('').props('fit=contain').classes('w-full h-full')
                    
                    # Navigation overlay
                    with ui.element('div').classes('absolute inset-0 flex items-center justify-between px-4 pointer-events-none'):
                        ui.button(icon='chevron_left', on_click=self._prev_preview_image).props('flat round color=white size=lg').classes('pointer-events-auto bg-black/30 hover:bg-black/50')
                        ui.button(icon='chevron_right', on_click=self._next_preview_image).props('flat round color=white size=lg').classes('pointer-events-auto bg-black/30 hover:bg-black/50')

    def _update_preview_content(self) -> None:
        """Update the content of the preview dialog based on current state."""
        if not self._preview_images or self._preview_index < 0 or self._preview_index >= len(self._preview_images):
            return
            
        data = self._preview_images[self._preview_index]
        path = data['path']
        name = data.get('name', Path(path).stem)
        
        full_path = self._working_folder / path
        
        if self._preview_image:
            self._preview_image.set_source(str(full_path))
        if self._preview_label:
            self._preview_label.set_text(name)

    def _next_preview_image(self) -> None:
        """Show next image in preview."""
        if self._preview_index < len(self._preview_images) - 1:
            self._preview_index += 1
            self._update_preview_content()

    def _prev_preview_image(self) -> None:
        """Show previous image in preview."""
        if self._preview_index > 0:
            self._preview_index -= 1
            self._update_preview_content()

    def _show_image_dialog(self, images: list[dict], start_index: int) -> None:
        """Show a dialog with the full-size image maximized.
        
        Args:
            images: List of image data dictionaries.
            start_index: Index of the image to start with.
        """
        if not self._preview_dialog:
            self._create_preview_dialog()
            
        self._preview_images = images
        self._preview_index = start_index
        self._update_preview_content()
        self._preview_dialog.open()

    def refresh(self) -> None:
        """Refresh the image manager display."""
        logger.debug(f"Refreshing ImageManager. Current tab: {self._current_tab}")
        # self._project.sync_with_filesystem()
        if self._container:
            self._container.clear()
            with self._container:
                self._build_ui()

    def get_selected_ids(self) -> list[str]:
        """Get list of selected image IDs."""
        return list(self._selected_ids)

    def select_image(self, image_id: str, selected: bool = True) -> None:
        """Select or deselect an image.
        
        Args:
            image_id: The image ID.
            selected: Whether to select (True) or deselect (False).
        """
        if selected:
            self._selected_ids.add(image_id)
        else:
            self._selected_ids.discard(image_id)
        
        if self._on_select:
            self._on_select(image_id)

    def clear_selection(self) -> None:
        """Clear all selections."""
        self._selected_ids.clear()
