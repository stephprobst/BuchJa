import logging
from pathlib import Path
from typing import Optional, Any, Callable
from nicegui import ui, app
from src.services.settings import Settings
from src.services.image_service import ImageService
from src.components.image_manager import ImageManager, ProjectManager
from src.components.status_footer import StatusFooter
from src.services.logging_config import configure_logging

logger = logging.getLogger(__name__)


class BuchJaApp:
    """Holds application state and lifecycle helpers."""

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
        self.check_settings_dirty: Optional[Callable[[], bool]] = None

        # Session state for tabs (preserved when switching)
        self.session_state: dict[str, Any] = {
            "generate_mode": "Create",  # 'Create' or 'Rework'
            "generate_type": "Page",  # 'Character Sheet' or 'Page'
            "generate_prompt": "",
            "selected_characters": {},
            "selected_references": {},
            "selected_rework_image": None,
            "sketch_data_url": None,
            "crop_source_image": None,
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

    def shutdown(self) -> None:
        """Shutdown the application server."""
        logger.info("Shutting down application...")
        if self.folder_watcher_timer:
            try:
                self.folder_watcher_timer.cancel()
            except Exception:
                pass
        app.shutdown()


APP = BuchJaApp()


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
                    model=getattr(usage, "model"),
                    prompt_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                    prompt_text_tokens=getattr(usage, "prompt_text_tokens", None),
                    prompt_image_tokens=getattr(usage, "prompt_image_tokens", None),
                    output_text_tokens=getattr(usage, "output_text_tokens", None),
                    output_image_tokens=getattr(usage, "output_image_tokens", None),
                    thoughts_tokens=getattr(usage, "thoughts_tokens", None),
                    cost=getattr(usage, "cost", None),
                )

            system_prompt_overrides = APP.settings.get_all_system_prompt_overrides()
            APP.image_service = ImageService(
                api_key,
                working_folder,
                usage_callback=record_usage,
                system_prompt_overrides=system_prompt_overrides,
            )
            APP.project_manager = ProjectManager(working_folder)
            logger.info("Image service initialized")
            return True
    return False
