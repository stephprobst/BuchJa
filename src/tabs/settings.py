from pathlib import Path
from nicegui import ui, app
from src.app import APP, init_image_service
from src.utils import start_folder_watcher
from src.services.settings import ASPECT_RATIOS
from src.services.image_service import SYSTEM_PROMPTS

GEMINI_PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"


def build_settings_tab():
    """Build the Settings tab content."""
    with ui.column().classes("w-full p-0 gap-0"):
        with ui.column().classes("w-full gap-6 p-4"):
            # API Configuration
            with ui.card().classes("w-full"):
                ui.label("API Configuration").classes("text-lg font-bold")

                ui.markdown(
                    "**DISCLAIMER & COST WARNING:** Usage of this application involves calls to Google's Gemini API, which may incur significant costs. "
                    "You are solely responsible for monitoring and paying for your API usage. "
                    "The token counter provided herein is an estimate only and should not be relied upon for billing purposes. "
                    "Always verify actual usage and costs via the Google Cloud Console or AI Studio. "
                    "The authors of this software accept no liability for any costs, damages, or data loss incurred. "
                    "By using this tool, you acknowledge that your data is processed by Google's services and is subject to their Terms of Service and Privacy Policy."
                ).classes("text-red-600 text-sm mb-1")

                with ui.row().classes("gap-4 mb-4"):
                    ui.link("Gemini API Pricing", GEMINI_PRICING_URL).classes(
                        "text-primary underline"
                    ).props("target=_blank")
                    ui.link(
                        "Get API Key", "https://aistudio.google.com/app/apikey"
                    ).classes("text-primary underline").props("target=_blank")

                api_key_input = (
                    ui.input(
                        "API Key",
                        password=True,
                        password_toggle_button=True,
                    )
                    .classes("w-full")
                    .props("outlined")
                )
                api_key_input._props["marker"] = "api-key-input"

                if APP.settings and APP.settings.has_api_key():
                    api_key_input.value = "••••••••••••••••"
                    ui.label("✓ API key is saved").classes("text-green-600 text-sm")

            # Working Folder
            with ui.card().classes("w-full"):
                ui.label("Working Folder").classes("text-lg font-bold")

                folder_label = ui.label(
                    str(APP.settings.working_folder)
                    if APP.settings and APP.settings.working_folder
                    else "Not set"
                ).classes("text-gray-600")

                async def pick_folder():
                    FOLDER_DIALOG = 20
                    result = await app.native.main_window.create_file_dialog(
                        dialog_type=FOLDER_DIALOG,
                        allow_multiple=False,
                    )
                    if result:
                        folder_path = (
                            Path(result[0])
                            if isinstance(result, tuple)
                            else Path(result)
                        )
                        if APP.settings is None:
                            return
                        APP.settings.working_folder = folder_path
                        APP.ensure_logging()
                        folder_label.text = str(folder_path)

                        # Re-initialize services with new folder and restart folder watcher
                        init_image_service()
                        start_folder_watcher()
                        APP.trigger_refresh()

                        ui.notify(
                            f"Working folder set to: {folder_path}", type="positive"
                        )

                ui.button("Browse...", on_click=pick_folder).props("outline")

            # Aspect Ratio
            with ui.card().classes("w-full"):
                ui.label("Aspect Ratio (width:height)").classes("text-lg font-bold")

                with ui.row().classes("w-full gap-4"):
                    aspect_select = ui.select(
                        ASPECT_RATIOS,
                        value=APP.settings.aspect_ratio if APP.settings else "3:4",
                        label="Page Aspect Ratio",
                    ).classes("w-64")
                    aspect_select._props["marker"] = "aspect-ratio-select"

                    # Character Sheet Aspect Ratio (Optional)
                    char_aspect_options = {None: "Same as Page"}
                    for r in ASPECT_RATIOS:
                        char_aspect_options[r] = r

                    char_aspect_select = ui.select(
                        char_aspect_options,
                        value=APP.settings.character_sheet_aspect_ratio
                        if APP.settings
                        else None,
                        label="Character Sheet Aspect Ratio",
                    ).classes("w-64")
                    char_aspect_select._props["marker"] = "char-aspect-ratio-select"

            # Style Prompt (moved from separate section)
            with ui.card().classes("w-full"):
                ui.label("Book Style").classes("text-lg font-bold")
                ui.label(
                    "Describe the overall artistic style for your book. "
                    "This will be applied to all generated images."
                ).classes("text-gray-600 text-sm mb-2")

                style_textarea = (
                    ui.textarea(
                        "Style Prompt",
                        value=APP.settings.style_prompt if APP.settings else "",
                        placeholder="e.g., Whimsical watercolor style with soft pastel colors, "
                        "reminiscent of classic children's book illustrations...",
                    )
                    .classes("w-full")
                    .props("outlined rows=4")
                )
                style_textarea._props["marker"] = "style-prompt-input"

            # System Prompt Overrides (project-specific)
            with ui.card().classes("w-full"):
                ui.label("System Prompt Overrides").classes("text-lg font-bold")
                ui.label(
                    "Override default system prompts for this project. "
                    "Leave empty to use defaults from ai_config.json."
                ).classes("text-gray-600 text-sm mb-2")

                with ui.expansion("Character Sheet Prompt", icon="person").classes(
                    "w-full"
                ):
                    default_char = SYSTEM_PROMPTS.get("character_sheet", "")
                    current_char = (
                        APP.settings.get_system_prompt_override("character_sheet")
                        if APP.settings
                        else None
                    )
                    ui.label("Default:").classes("text-xs text-gray-500 mt-2")
                    ui.label(default_char).classes(
                        "text-xs text-gray-400 italic mb-2 whitespace-pre-wrap select-text cursor-text"
                    )
                    char_sheet_textarea = (
                        ui.textarea(
                            "Custom Override (leave empty to use default)",
                            value=current_char or "",
                            placeholder=default_char,
                        )
                        .classes("w-full")
                        .props("outlined rows=4")
                    )
                    char_sheet_textarea._props["marker"] = "char-sheet-prompt-input"

                with ui.expansion("Page Prompt", icon="image").classes("w-full"):
                    default_page = SYSTEM_PROMPTS.get("page", "")
                    current_page = (
                        APP.settings.get_system_prompt_override("page")
                        if APP.settings
                        else None
                    )
                    ui.label("Default:").classes("text-xs text-gray-500 mt-2")
                    ui.label(default_page).classes(
                        "text-xs text-gray-400 italic mb-2 whitespace-pre-wrap select-text cursor-text"
                    )
                    page_textarea = (
                        ui.textarea(
                            "Custom Override (leave empty to use default)",
                            value=current_page or "",
                            placeholder=default_page,
                        )
                        .classes("w-full")
                        .props("outlined rows=4")
                    )
                    page_textarea._props["marker"] = "page-prompt-input"

                with ui.expansion("Rework Character Prompt", icon="edit").classes(
                    "w-full"
                ):
                    default_rework_char = SYSTEM_PROMPTS.get("rework_character", "")
                    current_rework_char = (
                        APP.settings.get_system_prompt_override("rework_character")
                        if APP.settings
                        else None
                    )
                    ui.label("Default:").classes("text-xs text-gray-500 mt-2")
                    ui.label(default_rework_char).classes(
                        "text-xs text-gray-400 italic mb-2 whitespace-pre-wrap select-text cursor-text"
                    )
                    rework_char_textarea = (
                        ui.textarea(
                            "Custom Override (leave empty to use default)",
                            value=current_rework_char or "",
                            placeholder=default_rework_char,
                        )
                        .classes("w-full")
                        .props("outlined rows=4")
                    )
                    rework_char_textarea._props["marker"] = "rework-char-prompt-input"

                with ui.expansion("Rework Page Prompt", icon="auto_fix_high").classes(
                    "w-full"
                ):
                    default_rework_page = SYSTEM_PROMPTS.get("rework_page", "")
                    current_rework_page = (
                        APP.settings.get_system_prompt_override("rework_page")
                        if APP.settings
                        else None
                    )
                    ui.label("Default:").classes("text-xs text-gray-500 mt-2")
                    ui.label(default_rework_page).classes(
                        "text-xs text-gray-400 italic mb-2 whitespace-pre-wrap select-text cursor-text"
                    )
                    rework_page_textarea = (
                        ui.textarea(
                            "Custom Override (leave empty to use default)",
                            value=current_rework_page or "",
                            placeholder=default_rework_page,
                        )
                        .classes("w-full")
                        .props("outlined rows=4")
                    )
                    rework_page_textarea._props["marker"] = "rework-page-prompt-input"

        def check_dirty() -> bool:
            if not APP.settings:
                return False

            # API Key: Dirty if user typed something (value is not empty) AND it's not the masked value
            if api_key_input.value and not api_key_input.value.startswith("•"):
                return True

            # Aspect Ratio
            if aspect_select.value != APP.settings.aspect_ratio:
                return True

            # Character Sheet Aspect Ratio
            if char_aspect_select.value != APP.settings.character_sheet_aspect_ratio:
                return True

            # Style Prompt
            if style_textarea.value != APP.settings.style_prompt:
                return True

            # System Prompt Overrides
            for key, textarea in [
                ("character_sheet", char_sheet_textarea),
                ("page", page_textarea),
                ("rework_character", rework_char_textarea),
                ("rework_page", rework_page_textarea),
            ]:
                current_override = APP.settings.get_system_prompt_override(key) or ""
                if textarea.value != current_override:
                    return True

            return False

        APP.check_settings_dirty = check_dirty

        # Save Button
        def save_settings():
            if APP.settings:
                with APP.settings.batch_updates():
                    if api_key_input.value and not api_key_input.value.startswith("•"):
                        APP.settings.set_api_key(api_key_input.value)
                        api_key_input.value = "••••••••••••••••"

                    APP.settings.aspect_ratio = aspect_select.value
                    APP.settings.character_sheet_aspect_ratio = char_aspect_select.value
                    APP.settings.style_prompt = style_textarea.value

                    # Save system prompt overrides
                    for key, textarea in [
                        ("character_sheet", char_sheet_textarea),
                        ("page", page_textarea),
                        ("rework_character", rework_char_textarea),
                        ("rework_page", rework_page_textarea),
                    ]:
                        APP.settings.set_system_prompt_override(key, textarea.value)

                # Update image service with new overrides
                if APP.image_service:
                    APP.image_service.set_system_prompt_overrides(
                        APP.settings.get_all_system_prompt_overrides()
                    )

                APP.ensure_logging()

                if init_image_service():
                    start_folder_watcher()
                    ui.notify("Settings saved successfully!", type="positive")
                    APP.trigger_refresh()
                else:
                    ui.notify(
                        "Settings saved. Configure API key and working folder to enable generation.",
                        type="warning",
                    )
                    APP.trigger_refresh()

        with ui.row().classes(
            "sticky bottom-0 w-full bg-white p-4 border-t z-10 justify-end shadow-lg"
        ):
            ui.button("Save Settings", on_click=save_settings, icon="save").props(
                "color=primary"
            )
