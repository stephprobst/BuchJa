"""Book Creator - Main Application Entry Point.

A NiceGUI-based desktop application for creating illustrated books
using Google's Gemini image generation API.

This module implements a vertical tab-based UI with five main sections:
- Settings: API configuration, working folder, aspect ratio, and style
- Add: Upload references
- Crop: Crop elements from existing images
- Generate: Create new images or rework existing ones (character sheets/pages)
- Manage: Organize images and export to PDF
"""

import asyncio
import html
import logging
import uuid
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable
import hashlib
import logging
import html
import asyncio

from nicegui import app, ui

from src.services.settings import Settings, ASPECT_RATIOS
from src.services.image_service import ImageService, ImageGenerationError, SYSTEM_PROMPTS, TEMPLATES
from src.components.image_manager import ImageManager, ProjectManager
from src.components.status_footer import StatusFooter
from src.components.sketch_canvas import SketchCanvas, save_sketch_to_file
from src.components.image_cropper import ImageCropper, save_cropped_image, image_to_data_url
from src.services.logging_config import configure_logging

GEMINI_PRICING_URL = 'https://ai.google.dev/gemini-api/docs/pricing'

logger = logging.getLogger(__name__)


class BookCreatorApp:
    """Holds application state and lifecycle helpers.

    NiceGUI pages and callbacks run in an event-driven context; keeping state
    in one object avoids scattered module-level globals and makes it easier to
    reason about initialization and future testability.
    """

    def __init__(self) -> None:
        self.settings: Optional[Settings] = None
        self.image_service: Optional[ImageService] = None
        self.project_manager: Optional[ProjectManager] = None
        self.image_manager: Optional[ImageManager] = None
        self.status_footer: Optional[StatusFooter] = None
        self.folder_watcher_timer: Optional[Any] = None
        self.last_folder_state: dict[str, set[str]] = {}
        self.log_file: Optional[Path] = None
        self.refresh_callbacks: list[Callable[[], None]] = []
        
        # Session state for tabs (preserved when switching)
        self.session_state: dict[str, Any] = {
            # Generate tab state
            'generate_mode': 'Create',  # 'Create' or 'Rework'
            'generate_type': 'Page',    # 'Character Sheet' or 'Page'
            'generate_prompt': '',
            'selected_characters': {},
            'selected_references': {},
            'selected_rework_image': None,
            'sketch_data_url': None,
            # Add tab state
            'crop_source_image': None,
        }

    def register_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when folders change."""
        self.refresh_callbacks.append(callback)
        
        try:
            # Remove callback when client disconnects
            def remove():
                if callback in self.refresh_callbacks:
                    self.refresh_callbacks.remove(callback)
            ui.context.client.on_disconnect(remove)
        except Exception:
            # Might be called outside of context (e.g. tests), ignore
            pass
        
    def trigger_refresh(self) -> None:
        """Trigger all registered refresh callbacks."""
        for callback in self.refresh_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in refresh callback: {e}")

    def ensure_logging(self) -> None:
        """Configure stdout + file logging.

        The file log goes into the *current project folder* (working folder) if
        configured, otherwise falls back to the current working directory.
        """
        project_folder = None
        if self.settings is not None and self.settings.working_folder is not None:
            project_folder = self.settings.working_folder
        self.log_file = configure_logging(project_folder=project_folder)


APP = BookCreatorApp()


def notify_error(message: str) -> None:
    """Show a non-auto-dismissing error notification."""
    ui.notify(message, type='negative', timeout=0)


def init_services():
    """Initialize application services."""
    APP.settings = Settings()
    APP.ensure_logging()


def init_image_service():
    """Initialize image service with current settings."""
    if APP.settings and APP.settings.is_configured():
        api_key = APP.settings.get_api_key()
        working_folder = APP.settings.working_folder
        
        if api_key and working_folder:
            def record_usage(usage) -> None:
                if APP.settings is None:
                    return
                APP.settings.record_gemini_usage(
                    model=getattr(usage, 'model'),
                    prompt_tokens=getattr(usage, 'prompt_tokens', None),
                    output_tokens=getattr(usage, 'output_tokens', None),
                    total_tokens=getattr(usage, 'total_tokens', None),
                    prompt_text_tokens=getattr(usage, 'prompt_text_tokens', None),
                    prompt_image_tokens=getattr(usage, 'prompt_image_tokens', None),
                    output_text_tokens=getattr(usage, 'output_text_tokens', None),
                    output_image_tokens=getattr(usage, 'output_image_tokens', None),
                    thoughts_tokens=getattr(usage, 'thoughts_tokens', None),
                    cost=getattr(usage, 'cost', None),
                )

            APP.image_service = ImageService(api_key, working_folder, usage_callback=record_usage)
            APP.project_manager = ProjectManager(working_folder)
            logger.info("Image service initialized")
            return True
    return False


def _format_since(iso: Optional[str]) -> str:
    if not iso:
        return '—'
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso


def _usage_text() -> tuple[str, str, Optional[str], bool]:
    """Return (tokens_text, since_text, cost_text, has_cost)."""
    if APP.settings is None:
        return ('Tokens: —', 'Since: —', None, False)

    usage = APP.settings.get_gemini_usage()
    if not isinstance(usage, dict):
        return ('Tokens: —', 'Since: —', None, False)

    totals = usage.get('totals') if isinstance(usage.get('totals'), dict) else {}
    total_tokens = int(totals.get('total_tokens', 0) or 0)
    tokens_text = f"Tokens: {total_tokens}"
    since_text = f"Since: {_format_since(usage.get('since'))}"
    cost = usage.get('cost')
    if cost is None:
        return (tokens_text, since_text, None, False)
    return (tokens_text, since_text, f"Cost: {cost}", True)


def _usage_tooltip_text() -> str:
    if APP.settings is None:
        return 'Gemini usage is unavailable.'

    usage = APP.settings.get_gemini_usage()
    if not isinstance(usage, dict):
        return 'Gemini usage is unavailable.'

    models = usage.get('models')
    if not isinstance(models, dict) or not models:
        totals = usage.get('totals') if isinstance(usage.get('totals'), dict) else {}
        return (
            f"Prompt tokens: {int(totals.get('prompt_tokens', 0) or 0)}\n"
            f"Output tokens: {int(totals.get('output_tokens', 0) or 0)}\n"
            f"Thinking tokens: {int(totals.get('thoughts_tokens', 0) or 0)}"
        )

    lines: list[str] = []
    for model_name, m in models.items():
        if not isinstance(m, dict):
            continue
        lines.append(model_name)
        lines.append(
            f"  input text: {int(m.get('prompt_text_tokens', 0) or 0)}  "
            f"input image: {int(m.get('prompt_image_tokens', 0) or 0)}"
        )
        lines.append(
            f"  output text: {int(m.get('output_text_tokens', 0) or 0)}  "
            f"output thinking: {int(m.get('thoughts_tokens', 0) or 0)}  "
            f"output image: {int(m.get('output_image_tokens', 0) or 0)}"
        )
        lines.append(
            f"  totals: {int(m.get('total_tokens', 0) or 0)} (p{int(m.get('prompt_tokens', 0) or 0)}/o{int(m.get('output_tokens', 0) or 0)})"
        )
    return "\n".join(lines).strip() or 'Gemini usage is unavailable.'


def _tooltip_html_from_text(text: str) -> str:
    """Render tooltip text with reliable line breaks using HTML."""
    escaped = html.escape(text or '')
    rendered_lines: list[str] = []
    for line in escaped.split('\n'):
        leading = len(line) - len(line.lstrip(' '))
        rendered_lines.append('&nbsp;' * leading + line.lstrip(' '))
    return '<br>'.join(rendered_lines)


def get_folder_hash(folder_path: Path) -> str:
    """Calculate a hash of all filenames in the folder."""
    if not folder_path.exists():
        return ""
    
    # Get all files, sort them to ensure consistent order
    files = sorted([f.name for f in folder_path.iterdir() if f.is_file()])
    
    # Create a hash of the concatenated filenames
    hasher = hashlib.md5()
    for filename in files:
        hasher.update(filename.encode('utf-8'))
    
    return hasher.hexdigest()


def get_folder_state() -> dict:
    """Get current state of monitored folders using hashes."""
    state = {}
    if not APP.settings or not APP.settings.working_folder:
        return state
    
    folders_to_watch = ['inputs', 'references', 'pages']
    
    for folder_name in folders_to_watch:
        folder = APP.settings.get_subfolder(folder_name)
        if folder:
            state[folder_name] = get_folder_hash(folder)
        else:
            state[folder_name] = ""
    
    return state


def check_folder_changes() -> None:
    """Check for folder changes and refresh UI if needed."""
    current_state = get_folder_state()
    
    if current_state != APP.last_folder_state:
        logger.info("Folder changes detected, refreshing...")
        
        APP.last_folder_state = current_state
        
        if APP.image_manager:
            APP.image_manager.refresh()
            
        APP.trigger_refresh()


def start_folder_watcher() -> None:
    """Start the folder watcher timer."""
    APP.last_folder_state = get_folder_state()
    
    # Always restart the timer to ensure it's bound to the current client/page
    if APP.folder_watcher_timer:
        try:
            APP.folder_watcher_timer.cancel()
        except Exception:
            pass
        APP.folder_watcher_timer = None

    APP.folder_watcher_timer = ui.timer(3.0, check_folder_changes)
    logger.info("Folder watcher started (3s interval)")


def stop_folder_watcher() -> None:
    """Stop the folder watcher timer."""
    if APP.folder_watcher_timer:
        APP.folder_watcher_timer.cancel()
        APP.folder_watcher_timer = None
        logger.info("Folder watcher stopped")


# =============================================================================
# Tab Panel Builders
# =============================================================================

def build_settings_tab():
    """Build the Settings tab content."""
    with ui.column().classes('w-full gap-6 p-4'):
        # API Configuration
        with ui.card().classes('w-full'):
            ui.label('API Configuration').classes('text-lg font-bold')
            
            ui.markdown(
                '**DISCLAIMER & COST WARNING:** Usage of this application involves calls to Google\'s Gemini API, which may incur significant costs. '
                'You are solely responsible for monitoring and paying for your API usage. '
                'The token counter provided herein is an estimate only and should not be relied upon for billing purposes. '
                'Always verify actual usage and costs via the Google Cloud Console or AI Studio. '
                'The authors of this software accept no liability for any costs, damages, or data loss incurred. '
                'By using this tool, you acknowledge that your data is processed by Google\'s services and is subject to their Terms of Service and Privacy Policy.'
            ).classes('text-red-600 text-sm mb-1')
            
            with ui.row().classes('gap-4 mb-4'):
                ui.link('Gemini API Pricing', GEMINI_PRICING_URL).classes('text-primary underline').props('target=_blank')
                ui.link('Get API Key', 'https://aistudio.google.com/app/apikey').classes('text-primary underline').props('target=_blank')

            api_key_input = ui.input(
                'API Key',
                password=True,
                password_toggle_button=True,
            ).classes('w-full').props('outlined')
            api_key_input._props['marker'] = 'api-key-input'
            
            if APP.settings and APP.settings.has_api_key():
                api_key_input.value = '••••••••••••••••'
                ui.label('✓ API key is saved').classes('text-green-600 text-sm')
        
        # Working Folder
        with ui.card().classes('w-full'):
            ui.label('Working Folder').classes('text-lg font-bold')
            
            folder_label = ui.label(
                str(APP.settings.working_folder) if APP.settings and APP.settings.working_folder else 'Not set'
            ).classes('text-gray-600')
            
            async def pick_folder():
                FOLDER_DIALOG = 20
                result = await app.native.main_window.create_file_dialog(
                    dialog_type=FOLDER_DIALOG,
                    allow_multiple=False,
                )
                if result:
                    folder_path = Path(result[0]) if isinstance(result, tuple) else Path(result)
                    if APP.settings is None:
                        return
                    APP.settings.working_folder = folder_path
                    APP.ensure_logging()
                    folder_label.text = str(folder_path)
                    ui.notify(f'Working folder set to: {folder_path}', type='positive')
            
            ui.button('Browse...', on_click=pick_folder).props('outline')
        
        # Aspect Ratio
        with ui.card().classes('w-full'):
            ui.label('Aspect Ratio').classes('text-lg font-bold')
            
            aspect_select = ui.select(
                ASPECT_RATIOS,
                value=APP.settings.aspect_ratio if APP.settings else '3:4',
                label='Page Aspect Ratio'
            ).classes('w-48')
            aspect_select._props['marker'] = 'aspect-ratio-select'
        
        # Style Prompt (moved from separate section)
        with ui.card().classes('w-full'):
            ui.label('Book Style').classes('text-lg font-bold')
            ui.label(
                'Describe the overall artistic style for your book. '
                'This will be applied to all generated images.'
            ).classes('text-gray-600 text-sm mb-2')
            
            style_textarea = ui.textarea(
                'Style Prompt',
                value=APP.settings.style_prompt if APP.settings else '',
                placeholder='e.g., Whimsical watercolor style with soft pastel colors, '
                           'reminiscent of classic children\'s book illustrations...'
            ).classes('w-full').props('outlined rows=4')
            style_textarea._props['marker'] = 'style-prompt-input'
        
        # Save Button
        def save_settings():
            if APP.settings:
                if api_key_input.value and not api_key_input.value.startswith('•'):
                    APP.settings.set_api_key(api_key_input.value)
                    api_key_input.value = '••••••••••••••••'
                
                APP.settings.aspect_ratio = aspect_select.value
                APP.settings.style_prompt = style_textarea.value
                APP.ensure_logging()
                
                if init_image_service():
                    start_folder_watcher()
                    ui.notify('Settings saved successfully!', type='positive')
                else:
                    ui.notify('Settings saved. Configure API key and working folder to enable generation.', type='warning')
        
        ui.button('Save Settings', on_click=save_settings, icon='save').props('color=primary')


def build_add_tab():
    """Build the Add tab content for uploading images."""
    with ui.column().classes('w-full gap-6 p-4'):
        # Upload Section
        with ui.card().classes('w-full'):
            ui.label('Upload Reference Images').classes('text-lg font-bold')
            ui.label(
                'Upload photos or reference images to use for character creation and scene generation.'
            ).classes('text-gray-600 text-sm mb-4')
            
            async def handle_upload(e):
                if not APP.settings or not APP.settings.working_folder:
                    notify_error('Please set a working folder first!')
                    return
                
                input_folder = APP.settings.get_subfolder('inputs')
                if input_folder:
                    file_path = input_folder / e.file.name
                    await e.file.save(file_path)
                    ui.notify(f'Uploaded: {e.file.name}', type='positive')
                    
                    if APP.project_manager:
                        # APP.project_manager.add_image(file_path, 'inputs', file_path.stem)
                        pass
                    
                    check_folder_changes()
            
            ui.upload(
                label='Drop images here or click to upload',
                on_upload=handle_upload,
                multiple=True,
                auto_upload=True,
            ).classes('w-full').props('accept="image/*"')
            
            ui.label(
                'Tip: You can also copy images directly into the "inputs" folder in your working directory.'
            ).classes('text-gray-500 text-xs mt-2')


def build_crop_tab():
    """Build the Crop tab content for cropping elements from existing images."""
    with ui.column().classes('w-full gap-6 p-4'):
        # Crop from Existing Section
        with ui.card().classes('w-full'):
            ui.label('Crop from Existing Image').classes('text-lg font-bold')
            ui.label(
                'Select an existing image and crop a portion to create a new reference image.'
            ).classes('text-gray-600 text-sm mb-4')
            
            # Image selection grid
            crop_source_container = ui.element('div').classes('w-full')
            cropper_container = ui.element('div').classes('w-full mt-4')
            cropper_instance: list[Optional[ImageCropper]] = [None]
            selected_source_path: list[Optional[Path]] = [None]
            
            def build_crop_source_grid():
                crop_source_container.clear()
                with crop_source_container:
                    if not APP.project_manager or not APP.settings:
                        ui.label('Please configure settings first.').classes('text-gray-500 text-sm')
                        return
                    
                    # Get all images from all categories
                    all_images = []
                    for category in ['inputs', 'references', 'pages']:
                        images = APP.project_manager.get_images(category)
                        for img in images:
                            img['_category'] = category
                            all_images.append(img)
                    
                    if not all_images:
                        ui.label('No images available. Upload some images first.').classes('text-gray-500 text-sm')
                        return
                    
                    ui.label('Select an image to crop:').classes('text-sm font-medium mb-2')
                    
                    with ui.element('div').classes('grid grid-cols-6 gap-2'):
                        for img in all_images:
                            img_path = img.get('path')
                            img_name = img.get('name', Path(img_path).stem if img_path else 'Unknown')
                            
                            if img_path:
                                full_path = Path(img_path)
                                if not full_path.is_absolute():
                                    full_path = APP.settings.working_folder / img_path
                                
                                thumb_path = None
                                if APP.image_service:
                                    try:
                                        thumb_path = APP.image_service.ensure_thumbnail(full_path)
                                    except Exception as e:
                                        logger.warning(f"Failed to ensure thumbnail for {full_path}: {e}")
                                
                                if not thumb_path:
                                    thumb_path = APP.settings.working_folder / ".thumbnails" / f"{full_path.stem}_thumb.png"

                                display_path = thumb_path if thumb_path.exists() else full_path
                                
                                if display_path.exists():
                                    with ui.card().classes('cursor-pointer p-1 hover:shadow-md transition-shadow') as card:
                                        with ui.element('div').classes('w-full h-16 bg-gray-100 flex items-center justify-center rounded'):
                                            ui.image(str(display_path)).props('fit=contain').classes('w-full h-full')
                                        ui.label(img_name[:12]).classes('text-xs truncate text-center')
                                        
                                        def select_for_crop(card=card, path=full_path):
                                            selected_source_path[0] = path
                                            load_image_for_cropping(path)
                                        
                                        card.on('click', select_for_crop)
            
            def load_image_for_cropping(image_path: Path):
                cropper_container.clear()
                with cropper_container:
                    ui.label(f'Cropping: {image_path.name}').classes('text-sm font-medium mb-2')
                    
                    def on_crop(data_url: str):
                        if not APP.settings or not APP.settings.working_folder:
                            notify_error('Working folder not configured!')
                            return
                        
                        input_folder = APP.settings.get_subfolder('inputs')
                        if input_folder:
                            timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                            crop_filename = f"crop_{timestamp}.png"
                            crop_path = input_folder / crop_filename
                            save_cropped_image(data_url, crop_path)
                            
                            # if APP.project_manager:
                            #     APP.project_manager.add_image(crop_path, 'inputs', crop_path.stem)
                            
                            ui.notify(f'Cropped image saved: {crop_filename}', type='positive')
                            check_folder_changes()
                            build_crop_source_grid()  # Refresh to show new image
                    
                    def on_error(error_msg: str):
                        notify_error(f'Crop error: {error_msg}')
                    
                    cropper = ImageCropper(
                        initial_aspect_ratio='free',
                        on_crop=on_crop,
                        on_error=on_error,
                    )
                    cropper_instance[0] = cropper
                    
                    # Load the image into cropper
                    data_url = image_to_data_url(image_path)
                    ui.timer(0.5, lambda: cropper.load_image(data_url), once=True)
            
            # Initial build
            build_crop_source_grid()
            
            ui.button('↻ Refresh Images', on_click=build_crop_source_grid).props('flat dense').classes('mt-2')

    # Register refresh callbacks
    APP.register_refresh_callback(build_crop_source_grid)


def build_generate_tab():
    """Build the Generate tab content with unified creation interface."""
    with ui.column().classes('w-full gap-4 p-4'):
        # Mode toggles
        with ui.card().classes('w-full'):
            with ui.row().classes('gap-8 items-center'):
                with ui.row().classes('items-center gap-2'):
                    mode_switch = ui.switch(
                        'Rework Mode',
                        value=APP.session_state.get('generate_mode') == 'Rework',
                    ).props('color=primary')
                    mode_switch._props['marker'] = 'generate-mode-toggle'
                    with ui.icon('info', size='xs').classes('text-gray-400 cursor-help'):
                        ui.tooltip('Enable to generate a new image as modification of an existing one.')
                
                with ui.row().classes('items-center gap-2'):
                    type_switch = ui.switch(
                        'Character Sheet',
                        value=APP.session_state.get('generate_type') == 'Character Sheet',
                    ).props('color=secondary')
                    type_switch._props['marker'] = 'generate-type-toggle'
                    with ui.icon('info', size='xs').classes('text-gray-400 cursor-help'):
                        ui.tooltip('Enable to generate a character reference sheet. Disable to generate a story page.')
                
                resolution_select = ui.select(
                    ['1K', '2K', '4K'],
                    value=APP.session_state.get('generate_resolution', '4K'),
                    label='Resolution'
                ).classes('w-32').props('outlined dense')
                resolution_select._props['marker'] = 'generate-resolution-select'

                with ui.row().classes('items-center gap-1'):
                    p_threshold_input = ui.number(
                        'P-Threshold',
                        value=APP.settings.p_threshold if APP.settings else 0.95,
                        min=0.0, max=1.0, step=0.05,
                        format='%.2f'
                    ).classes('w-28').props('outlined dense')
                    with ui.icon('info', size='xs').classes('text-gray-400 cursor-help'):
                        ui.tooltip('Controls randomness: Lower values make responses more deterministic.')
                
                with ui.row().classes('items-center gap-1'):
                    temperature_input = ui.number(
                        'Temperature',
                        value=APP.settings.temperature if APP.settings else 1.0,
                        min=0.0, max=2.0, step=0.1,
                        format='%.1f'
                    ).classes('w-28').props('outlined dense')
                    with ui.icon('info', size='xs').classes('text-gray-400 cursor-help'):
                        ui.tooltip('Controls creativity: Higher values make output more random/creative.')
        
        # Rework source selection (only visible in Rework mode)
        rework_section = ui.column().classes('w-full')
        rework_source_path: list[Optional[Path]] = [None]
        
        def build_rework_source_selector():
            rework_section.clear()
            with rework_section:
                if not mode_switch.value:
                    return
                
                with ui.card().classes('w-full'):
                    ui.label('Select Image to Rework').classes('text-lg font-bold')
                    ui.label('Choose the original image you want to modify.').classes('text-gray-600 text-sm mb-4')
                    
                    if not APP.project_manager or not APP.settings:
                        ui.label('Please configure settings first.').classes('text-gray-500 text-sm')
                        return
                    
                    # Get images based on type
                    category = 'references' if type_switch.value else 'pages'
                    images = APP.project_manager.get_images(category)
                    
                    if not images:
                        ui.label(f'No {category} available to rework.').classes('text-gray-500 text-sm')
                        return
                    
                    rework_grid = ui.element('div').classes('grid grid-cols-4 gap-2')
                    
                    with rework_grid:
                        for img in images:
                            img_id = img.get('id')
                            img_path = img.get('path')
                            img_name = img.get('name', Path(img_path).stem if img_path else 'Unknown')
                            
                            if img_path:
                                full_path = Path(img_path)
                                if not full_path.is_absolute():
                                    full_path = APP.settings.working_folder / img_path
                                
                                thumb_path = None
                                if APP.image_service:
                                    try:
                                        thumb_path = APP.image_service.ensure_thumbnail(full_path)
                                    except Exception as e:
                                        logger.warning(f"Failed to ensure thumbnail for {full_path}: {e}")
                                
                                if not thumb_path:
                                    thumb_path = APP.settings.working_folder / ".thumbnails" / f"{full_path.stem}_thumb.png"

                                display_path = thumb_path if thumb_path.exists() else full_path
                                
                                if display_path.exists():
                                    is_selected = rework_source_path[0] == full_path
                                    
                                    with ui.card().classes('cursor-pointer p-1 hover:shadow-md transition-shadow') as card:
                                        if is_selected:
                                            card.style('border: 2px solid #10b981;')
                                        else:
                                            card.style('border: 2px solid transparent;')
                                        
                                        with ui.element('div').classes('w-full h-20 bg-gray-100 flex items-center justify-center rounded'):
                                            ui.image(str(display_path)).props('fit=contain').classes('w-full h-full')
                                        ui.label(img_name[:15]).classes('text-xs truncate text-center')
                                        
                                        def select_rework(card=card, path=full_path):
                                            rework_source_path[0] = path
                                            APP.session_state['selected_rework_image'] = path
                                            build_rework_source_selector()
                                        
                                        card.on('click', select_rework)
        
        # Reference selection state
        selected_references: dict[str, bool] = dict(APP.session_state.get('selected_references', {}))

        # Prompt input
        with ui.card().classes('w-full'):
            prompt_label = ui.label('Prompt').classes('text-lg font-bold')
            
            with ui.expansion('System Prompt', icon='settings_system_daydream').classes('w-full mb-2 bg-gray-50 rounded'):
                system_prompt_display = ui.label('').classes('text-sm text-gray-600 p-2 font-mono whitespace-pre-wrap break-words')
            
            description_input = ui.textarea(
                'Prompt',
                value=APP.session_state.get('generate_prompt', ''),
                placeholder='Describe what you want to create or how to modify the image...'
            ).classes('w-full').props('outlined rows=3')
            description_input._props['marker'] = 'generate-prompt-input'
            
            # Save prompt to session state on change
            def save_prompt():
                APP.session_state['generate_prompt'] = description_input.value
            description_input.on('blur', save_prompt)

            # Selected references display
            selected_refs_container = ui.row().classes('w-full gap-2 mt-2')
            
            def update_selected_refs_display():
                selected_refs_container.clear()
                if not APP.project_manager: return
                
                selected_ids = [rid for rid, selected in selected_references.items() if selected]
                if not selected_ids:
                    return

                # Fetch all images to find names
                all_imgs = []
                for cat in ['references', 'inputs', 'pages']:
                    all_imgs.extend(APP.project_manager.get_images(cat))
                
                id_to_name = {img['id']: img.get('name', Path(img['path']).stem) for img in all_imgs}
                
                with selected_refs_container:
                    for rid in selected_ids:
                        name = id_to_name.get(rid, 'Unknown')
                        ui.chip(name, icon='image', removable=True).on('remove', lambda e, rid=rid: remove_ref(rid))

            def remove_ref(rid):
                selected_references[rid] = False
                APP.session_state['selected_references'] = selected_references
                update_selected_refs_display()
                build_refs_grid()
        
        # Reference selection
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Select References').classes('text-lg font-bold')
                show_all_types = ui.switch('Show pages and inputs', value=False).props('dense')
            
            refs_grid = ui.element('div').classes('w-full')
            
            def build_refs_grid():
                refs_grid.clear()
                with refs_grid:
                    if not APP.project_manager or not APP.settings:
                        ui.label('Configure settings first.').classes('text-gray-500 text-sm')
                        return
                    
                    # Show references, inputs, and pages
                    references = APP.project_manager.get_images('references')
                    if show_all_types.value:
                        inputs = APP.project_manager.get_images('inputs')
                        pages = APP.project_manager.get_images('pages')
                        all_refs = references + inputs + pages
                    else:
                        all_refs = references
                    
                    if not all_refs:
                        ui.label('No images available.').classes('text-gray-500 text-sm')
                        return
                    
                    with ui.element('div').classes('grid grid-cols-6 gap-2 mt-2'):
                        for ref in all_refs:
                            ref_id = ref.get('id')
                            ref_path = ref.get('path')
                            ref_name = ref.get('name', Path(ref_path).stem if ref_path else 'Unknown')
                            
                            if ref_path:
                                full_path = Path(ref_path)
                                if not full_path.is_absolute():
                                    full_path = APP.settings.working_folder / full_path
                                
                                thumb_path = None
                                if APP.image_service:
                                    try:
                                        thumb_path = APP.image_service.ensure_thumbnail(full_path)
                                    except Exception as e:
                                        logger.warning(f"Failed to ensure thumbnail for {full_path}: {e}")
                                
                                if not thumb_path:
                                    thumb_path = APP.settings.working_folder / ".thumbnails" / f"{full_path.stem}_thumb.png"

                                display_path = thumb_path if thumb_path.exists() else full_path
                                
                                if display_path.exists():
                                    if ref_id not in selected_references:
                                        selected_references[ref_id] = False
                                    
                                    with ui.card().classes('cursor-pointer p-1 hover:shadow-md transition-shadow') as card:
                                        if selected_references.get(ref_id, False):
                                            card.style('border: 2px solid #6366f1;')
                                        else:
                                            card.style('border: 2px solid transparent;')
                                        
                                        with ui.element('div').classes('w-full h-16 bg-gray-100 flex items-center justify-center rounded'):
                                            ui.image(str(display_path)).props('fit=contain').classes('w-full h-full')
                                        ui.label(ref_name[:10]).classes('text-xs truncate text-center')
                                        
                                        def toggle_ref(card=card, rid=ref_id):
                                            selected_references[rid] = not selected_references.get(rid, False)
                                            APP.session_state['selected_references'] = selected_references
                                            if selected_references[rid]:
                                                card.style('border: 2px solid #6366f1;')
                                            else:
                                                card.style('border: 2px solid transparent;')
                                            update_selected_refs_display()
                                        
                                        card.on('click', toggle_ref)
            
            build_refs_grid()
            update_selected_refs_display()
            show_all_types.on('update:model-value', build_refs_grid)
            
            ui.button('↻ Refresh', on_click=build_refs_grid).props('flat dense').classes('mt-2')
        
        # Action buttons
        with ui.row().classes('gap-2 mt-4'):
            async def generate():
                if not APP.image_service:
                    notify_error('Please configure settings first!')
                    return
                
                prompt = (description_input.value or '').strip()
                if not prompt:
                    ui.notify('Please enter a description!', type='warning')
                    return
                
                if len(prompt) > 8000:
                    ui.notify('Description is too long (max 8000 characters).', type='warning')
                    return
                
                mode = 'Rework' if mode_switch.value else 'Create'
                gen_type = 'Character Sheet' if type_switch.value else 'Page'
                category = 'references' if gen_type == 'Character Sheet' else 'pages'
                system_key = 'character_sheet' if gen_type == 'Character Sheet' else 'page'
                resolution = resolution_select.value or '4K'
                
                # Collect selected references
                reference_images = []
                if APP.project_manager and APP.settings:
                    # Check all image categories for selected references
                    for category in ['references', 'inputs', 'pages']:
                        images = APP.project_manager.get_images(category)
                        for img in images:
                            if selected_references.get(img.get('id'), False):
                                img_path = img.get('path')
                                if img_path:
                                    full_path = Path(img_path)
                                    if not full_path.is_absolute():
                                        full_path = APP.settings.working_folder / full_path
                                    if full_path.exists():
                                        reference_images.append(full_path)
                
                try:
                    if mode == 'Create':
                        # Create new image
                        ui.notify(f'Generating {gen_type.lower()}...', type='info')
                        
                        if APP.status_footer:
                            async with APP.status_footer.busy(f'Generating {gen_type.lower()}...') as token:
                                image_path, thumb_path = await APP.image_service.generate_image(
                                    prompt=prompt,
                                    reference_images=reference_images if reference_images else None,
                                    style_prompt=APP.settings.style_prompt if APP.settings else '',
                                    aspect_ratio=APP.settings.aspect_ratio if APP.settings else '3:4',
                                    image_size=resolution,
                                    category=category,
                                    system_prompt_key=system_key,
                                    p_threshold=p_threshold_input.value,
                                    temperature=temperature_input.value,
                                    progress_callback=lambda m: APP.status_footer.update(m, token=token),
                                )
                        else:
                            image_path, thumb_path = await APP.image_service.generate_image(
                                prompt=prompt,
                                reference_images=reference_images if reference_images else None,
                                style_prompt=APP.settings.style_prompt if APP.settings else '',
                                aspect_ratio=APP.settings.aspect_ratio if APP.settings else '3:4',
                                image_size=resolution,
                                category=category,
                                system_prompt_key=system_key,
                                p_threshold=p_threshold_input.value,
                                temperature=temperature_input.value,
                            )
                    else:
                        # Rework existing image
                        if not rework_source_path[0]:
                            ui.notify('Please select an image to rework!', type='warning')
                            return
                        
                        ui.notify(f'Reworking {gen_type.lower()}...', type='info')
                        
                        if APP.status_footer:
                            async with APP.status_footer.busy(f'Reworking {gen_type.lower()}...') as token:
                                image_path, thumb_path = await APP.image_service.rework_image(
                                    original_image=rework_source_path[0],
                                    prompt=prompt,
                                    additional_references=reference_images if reference_images else None,
                                    style_prompt=APP.settings.style_prompt if APP.settings else '',
                                    aspect_ratio=APP.settings.aspect_ratio if APP.settings else '3:4',
                                    image_size=resolution,
                                    category=category,
                                    p_threshold=p_threshold_input.value,
                                    temperature=temperature_input.value,
                                    progress_callback=lambda m: APP.status_footer.update(m, token=token),
                                )
                        else:
                            image_path, thumb_path = await APP.image_service.rework_image(
                                original_image=rework_source_path[0],
                                prompt=prompt,
                                additional_references=reference_images if reference_images else None,
                                style_prompt=APP.settings.style_prompt if APP.settings else '',
                                aspect_ratio=APP.settings.aspect_ratio if APP.settings else '3:4',
                                image_size=resolution,
                                category=category,
                                p_threshold=p_threshold_input.value,
                                temperature=temperature_input.value,
                            )
                    
                    ui.notify(f'{gen_type} created: {image_path.name}', type='positive')
                    
                    # if APP.project_manager:
                    #     APP.project_manager.add_image(image_path, category, prompt[:50] if gen_type == 'Character Sheet' else None)
                    
                    if APP.image_manager:
                        APP.image_manager.refresh()
                
                except ImageGenerationError as e:
                    notify_error(f'Generation failed: {e}')
                except Exception as e:
                    logger.exception('Unexpected error during generation')
                    notify_error(f'Unexpected error: {e}')
            
            generate_btn = ui.button(
                'Generate',
                on_click=generate,
                icon='auto_awesome'
            ).props('color=primary')
            generate_btn._props['marker'] = 'generate-btn'
        
        # Update UI when mode changes
        def update_system_prompt_display():
            gen_type = 'Character Sheet' if type_switch.value else 'Page'
            system_key = 'character_sheet' if gen_type == 'Character Sheet' else 'page'
            # If rework mode, keys are different
            if mode_switch.value:
                system_key = "rework_page" if gen_type == 'Page' else "rework_character"
            
            prompt_text = SYSTEM_PROMPTS.get(system_key, "No system prompt found.")
            
            # Add style prompt to display
            if APP.settings and APP.settings.style_prompt:
                style_prefix = TEMPLATES.get("style_prefix", "Style: {style_prompt}")
                formatted_style = style_prefix.format(style_prompt=APP.settings.style_prompt)
                prompt_text += "\n\n" + formatted_style
                
            system_prompt_display.text = prompt_text

        def on_mode_change():
            APP.session_state['generate_mode'] = 'Rework' if mode_switch.value else 'Create'
            build_rework_source_selector()
            update_system_prompt_display()
        
        def on_type_change():
            APP.session_state['generate_type'] = 'Character Sheet' if type_switch.value else 'Page'
            if mode_switch.value:
                rework_source_path[0] = None
                APP.session_state['selected_rework_image'] = None
                build_rework_source_selector()
            update_system_prompt_display()
        
        def on_resolution_change():
            APP.session_state['generate_resolution'] = resolution_select.value

        def on_p_threshold_change():
            if APP.settings:
                APP.settings.p_threshold = p_threshold_input.value

        def on_temperature_change():
            if APP.settings:
                APP.settings.temperature = temperature_input.value

        mode_switch.on('update:model-value', on_mode_change)
        type_switch.on('update:model-value', on_type_change)
        resolution_select.on('update:model-value', on_resolution_change)
        p_threshold_input.on('change', on_p_threshold_change)
        temperature_input.on('change', on_temperature_change)
        
        # Initial build of rework section
        build_rework_source_selector()
        update_system_prompt_display()

        # Register refresh callbacks
        APP.register_refresh_callback(build_rework_source_selector)
        APP.register_refresh_callback(build_refs_grid)


def build_sketch_tab():
    """Build the Sketch tab content."""
    with ui.column().classes('w-full gap-6 p-4'):
        with ui.card().classes('w-full'):
            ui.label('Sketching Canvas').classes('text-lg font-bold')
            ui.label(
                'Draw a rough sketch to use as a reference for generation.'
            ).classes('text-gray-600 text-sm mb-4')
            
            with ui.row().classes('w-full items-center gap-4 mb-4'):
                filename_input = ui.input(
                    'Sketch Name',
                    value='my_sketch',
                    placeholder='Enter filename'
                ).classes('w-64')
                
                ui.label('Sketches are saved to the "References" folder.').classes('text-gray-500 text-sm italic')
            
            async def save_sketch(data_url: str):
                if not APP.settings or not APP.settings.working_folder:
                    notify_error('Please configure settings first!')
                    return
                
                if not data_url:
                    return

                try:
                    # Save to references folder
                    refs_folder = APP.settings.working_folder / 'references'
                    refs_folder.mkdir(parents=True, exist_ok=True)
                    
                    name = filename_input.value or 'sketch'
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{name}_{timestamp}.png"
                    file_path = refs_folder / filename
                    
                    save_sketch_to_file(data_url, file_path)
                    
                    # No need to call add_image as we saved directly to the folder
                    # and add_image would create a duplicate
                        
                    ui.notify(f'Sketch saved: {filename}', type='positive')
                    
                    # Refresh other tabs if needed
                    APP.trigger_refresh()
                    
                except Exception as e:
                    logger.exception('Failed to save sketch')
                    notify_error(f'Failed to save sketch: {e}')

            SketchCanvas(
                width=800,
                height=600,
                on_save=save_sketch,
                background_color='#ffffff'
            )


def build_instructions_tab():
    """Build the Instructions tab content."""
    with ui.column().classes('w-full gap-6 p-4 max-w-4xl'):
        with ui.card().classes('w-full'):
            ui.label('Welcome to Book Creator').classes('text-2xl font-bold mb-4')
            ui.label('This application helps you create illustrated books using AI. Follow the steps below to get started.').classes('text-gray-700 mb-4')

        with ui.card().classes('w-full'):
            ui.label('1. Setup').classes('text-xl font-bold mb-2')
            ui.markdown('''
            - Go to the **Settings** tab.
            - Enter your **Gemini API Key**.
            - Select a **Working Folder** where your project files will be stored.
            - Choose an **Aspect Ratio** for your book pages.
            - Enter a **Style Prompt** to define the artistic style of your illustrations.
            ''').classes('text-gray-700')

        with ui.card().classes('w-full'):
            ui.label('2. Add Input References').classes('text-xl font-bold mb-2')
            ui.markdown('''
            - Go to the **Add** tab.
            - Upload reference photos or images you want to use as inspiration.
            ''').classes('text-gray-700')

        with ui.card().classes('w-full'):
            ui.label('3. Create Character Sheets').classes('text-xl font-bold mb-2')
            ui.markdown('''
            - Go to the **Generate** tab.
            - Start creating  Character Reference Sheets first. These will help maintain consistency across your book.
            - Create and recreate them until you're happy with the designs.
            ''').classes('text-gray-700')

        with ui.card().classes('w-full'):
            ui.label('4. Generate Images').classes('text-xl font-bold mb-2')
            ui.markdown('''
            - Go to the **Generate** tab.
            - Choose **Create** mode to generate new images.
            - Select **Character Sheet** to design characters or **Page** for book illustrations.
            - Select reference images and/or draw a sketch to guide the AI.
            - Enter a prompt describing the scene or character.
            - Click **Generate**.
            - Use **Rework** mode to modify existing images while preserving the original composition.
            ''').classes('text-gray-700')

        with ui.card().classes('w-full'):
            ui.label('5. Manage & Export').classes('text-xl font-bold mb-2')
            ui.markdown('''
            - Go to the **Manage** tab.
            - Review your generated pages and characters.
            - Reorder pages as needed.
            - Export your book to a **PDF** file ready for printing or sharing.
            ''').classes('text-gray-700')


def build_manage_tab():
    """Build the Manage tab content for organizing images."""
    with ui.column().classes('w-full gap-6 p-4'):
        # Image Manager
        with ui.card().classes('w-full'):
            ui.label('Image Management').classes('text-lg font-bold')
            ui.label(
                'Review, reorder, and organize your book pages.'
            ).classes('text-gray-600 text-sm mb-4')
            
            manager_container = ui.column().classes('w-full')
            
            def init_manager():
                if APP.settings and APP.settings.working_folder and APP.project_manager:
                    with manager_container:
                        manager_container.clear()
                        APP.image_manager = ImageManager(
                            project_manager=APP.project_manager,
                            working_folder=APP.settings.working_folder,
                            image_service=APP.image_service
                        )
            
            init_manager()
            with ui.row().classes('gap-2'):
                ui.button('Refresh', on_click=init_manager, icon='refresh').props('outline')
                ui.button('OPEN IN FILE EXPLORER', on_click=lambda: APP.image_manager.open_current_folder() if APP.image_manager else None, icon='folder_open').props('outline')



def build_export_tab():
    """Build the Export tab content for creating PDFs."""
    with ui.column().classes('w-full gap-6 p-4'):
        with ui.card().classes('w-full'):
            ui.label('Export to PDF').classes('text-lg font-bold')
            ui.label(
                'Compile all ordered pages into a PDF document ready for printing.'
            ).classes('text-gray-600 text-sm mb-4')
            
            filename_input = ui.input(
                'Output Filename',
                value='my_book',
                placeholder='Enter filename (without .pdf)'
            ).classes('w-64')
            filename_input._props['marker'] = 'export-filename-input'
            
            async def export_pdf():
                if not APP.settings or not APP.settings.working_folder:
                    notify_error('Please configure settings first!')
                    return
                
                if not APP.project_manager:
                    notify_error('No project data found!')
                    return
                
                pages = APP.project_manager.get_ordered_pages()
                if not pages:
                    ui.notify('No pages to export!', type='warning')
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
                            raw_path = p.get('path')
                            if not raw_path:
                                continue
                            page_path = Path(raw_path)
                            if not page_path.is_absolute() and APP.settings and APP.settings.working_folder:
                                page_path = APP.settings.working_folder / page_path
                            page_paths.append(page_path)

                        if APP.status_footer:
                            async with APP.status_footer.busy('Exporting PDF...'):
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
                        ui.notify(f'PDF exported: {output_path}', type='positive')
                    except Exception as e:
                        logger.exception('PDF export failed')
                        notify_error(f'Export failed: {e}')
            
            def open_export_folder():
                if not APP.settings:
                    ui.notify('Settings not initialized', type='warning')
                    return
                
                folder = APP.settings.working_folder
                if not folder:
                    ui.notify('Working folder not configured', type='warning')
                    return
                
                if not folder.exists():
                    ui.notify(f'Folder does not exist: {folder}', type='warning')
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
                    ui.notify(f"Could not open folder: {e}", type='negative')

            with ui.row().classes('gap-2'):
                export_btn = ui.button(
                    'Export PDF',
                    on_click=export_pdf,
                    icon='download'
                ).props('color=primary')
                export_btn._props['marker'] = 'export-pdf-btn'

                ui.button(
                    'OPEN EXPORT FOLDER IN FILE EXPLORER',
                    on_click=open_export_folder,
                    icon='folder_open'
                ).props('outline')


# =============================================================================
# Main Application
# =============================================================================

@ui.page('/')
def main_page():
    """Main application page with vertical tab navigation."""
    # Add custom styles
    ui.add_head_html('''
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
    ''')

    # Initialize services
    init_services()
    if init_image_service():
        start_folder_watcher()
    
    # Header
    with ui.header().classes('bg-primary'):
        ui.label('📖 Book Creator').classes('text-2xl font-bold text-white')
        ui.label('Create illustrated books with AI').classes('text-white opacity-80 ml-4 self-end mb-1')
        ui.space()

        with ui.row().classes('items-center gap-4'):
            tokens_text, since_text, cost_text, has_cost = _usage_text()
            total_only = tokens_text

            usage_tokens_label = ui.label(total_only).classes('text-white')
            usage_tokens_label._props['marker'] = 'gemini-usage-tokens'
            with usage_tokens_label:
                with ui.tooltip():
                    usage_tooltip_html = ui.html(
                        _tooltip_html_from_text(_usage_tooltip_text()),
                        sanitize=False,
                    )

            usage_since_label = ui.label(since_text).classes('text-white opacity-80 text-sm')
            usage_since_label._props['marker'] = 'gemini-usage-since'

            usage_cost_label = ui.label(cost_text or '').classes('text-white')
            usage_cost_label._props['marker'] = 'gemini-usage-cost'
            usage_cost_label.set_visibility(has_cost)

            def refresh_usage_labels() -> None:
                t, s, c, has = _usage_text()
                usage_tokens_label.text = t
                usage_tooltip_html.content = _tooltip_html_from_text(_usage_tooltip_text())
                usage_since_label.text = s
                usage_cost_label.text = c or ''
                usage_cost_label.set_visibility(has)

            def reset_usage() -> None:
                if APP.settings is None:
                    return
                APP.settings.reset_gemini_usage()
                refresh_usage_labels()

            reset_btn = ui.button(icon='restart_alt', on_click=reset_usage).props('flat dense round').classes('text-white')
            reset_btn._props['marker'] = 'gemini-usage-reset-btn'
            reset_btn.tooltip('Reset Gemini usage counters')

            ui.timer(1.0, refresh_usage_labels)
    
    # Main content with vertical tabs
    with ui.element('div').classes('flex w-full h-full'):
        # Vertical tabs on the left
        with ui.element('div').classes('vertical-tabs'):
            with ui.tabs().props('vertical').classes('bg-gray-100 h-full') as tabs:
                instructions_tab = ui.tab('Instructions', icon='help')
                instructions_tab._props['marker'] = 'tab-instructions'
                settings_tab = ui.tab('Settings', icon='settings')
                settings_tab._props['marker'] = 'tab-settings'
                add_tab = ui.tab('Add', icon='add_photo_alternate')
                add_tab._props['marker'] = 'tab-add'
                crop_tab = ui.tab('Crop', icon='crop')
                crop_tab._props['marker'] = 'tab-crop'
                sketch_tab = ui.tab('Sketch', icon='brush')
                sketch_tab._props['marker'] = 'tab-sketch'
                generate_tab = ui.tab('Generate', icon='auto_awesome')
                generate_tab._props['marker'] = 'tab-generate'
                manage_tab = ui.tab('Manage', icon='folder')
                manage_tab._props['marker'] = 'tab-manage'
                export_tab = ui.tab('Export', icon='picture_as_pdf')
                export_tab._props['marker'] = 'tab-export'
        
        # Tab panels on the right (with keep-alive for state preservation)
        with ui.tab_panels(tabs, value=instructions_tab).props('keep-alive').classes('flex-1 overflow-auto'):
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


def main():
    """Application entry point."""
    ui.run(
        title='Book Creator',
        native=True,
        window_size=(1200, 800),
        reload=False,
    )


if __name__ in {'__main__', '__mp_main__'}:
    main()
