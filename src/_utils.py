import logging
import html
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from nicegui import ui
from src.services.image_service import ImageGenerationError
from src.app import APP

logger = logging.getLogger(__name__)


def notify_error(message: str, exception: Optional[Exception] = None) -> None:
    """Show an error dialog with details."""
    if exception:
        logger.error(message, exc_info=exception)
    else:
        logger.error(message)

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
        ui.label("Error").classes("text-h6 text-negative")
        ui.label(message).classes("text-body1 whitespace-pre-wrap")

        if (
            exception
            and isinstance(exception, ImageGenerationError)
            and getattr(exception, "is_api_error", False)
        ):
            ui.label("This appears to be an error from the Gemini API.").classes(
                "text-caption text-grey"
            )

        ui.separator().classes("my-2")

        ui.label("For more details, check the logs at:").classes(
            "text-caption font-bold"
        )
        log_path = APP.log_file if APP.log_file else "logs/BuchJa.log"
        ui.label(str(log_path)).classes(
            "text-caption text-grey break-all font-mono bg-gray-100 p-1 rounded"
        )

        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Copy Error", on_click=lambda: ui.clipboard.write(message)).props(
                "flat icon=content_copy"
            )
            ui.button("Close", on_click=dialog.close).props("flat icon=close")

    dialog.open()


def _format_since(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def usage_text() -> tuple[str, str, Optional[str], bool]:
    """Return (tokens_text, since_text, cost_text, has_cost)."""
    if APP.settings is None:
        return ("Tokens: —", "Since: —", None, False)

    usage = APP.settings.get_gemini_usage()
    if not isinstance(usage, dict):
        return ("Tokens: —", "Since: —", None, False)

    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    total_tokens = int(totals.get("total_tokens", 0) or 0)
    tokens_text = f"Tokens: {total_tokens}"
    since_text = f"Since: {_format_since(usage.get('since'))}"
    cost = usage.get("cost")
    if cost is None:
        return (tokens_text, since_text, None, False)
    return (tokens_text, since_text, f"Cost: {cost}", True)


def usage_tooltip_text() -> str:
    if APP.settings is None:
        return "Gemini usage is unavailable."

    usage = APP.settings.get_gemini_usage()
    if not isinstance(usage, dict):
        return "Gemini usage is unavailable."

    models = usage.get("models")
    if not isinstance(models, dict) or not models:
        totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
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
    return "\n".join(lines).strip() or "Gemini usage is unavailable."


def tooltip_html_from_text(text: str) -> str:
    """Render tooltip text with reliable line breaks using HTML."""
    escaped = html.escape(text or "")
    rendered_lines: list[str] = []
    for line in escaped.split("\n"):
        leading = len(line) - len(line.lstrip(" "))
        rendered_lines.append("&nbsp;" * leading + line.lstrip(" "))
    return "<br>".join(rendered_lines)


def get_folder_hash(folder_path: Path) -> str:
    """Calculate a hash of all filenames in the folder."""
    if not folder_path.exists():
        return ""

    files = sorted([f.name for f in folder_path.iterdir() if f.is_file()])
    hasher = hashlib.md5()
    for filename in files:
        hasher.update(filename.encode("utf-8"))
    return hasher.hexdigest()


def get_folder_state() -> dict:
    """Get current state of monitored folders using hashes."""
    state = {}
    if not APP.settings or not APP.settings.working_folder:
        return state

    folders_to_watch = ["inputs", "references", "pages"]

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
