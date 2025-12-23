import logging
from pathlib import Path
from typing import Optional
from nicegui import ui
from src.app import APP
from src._utils import notify_error
from src.services.image_service import ImageGenerationError, SYSTEM_PROMPTS, TEMPLATES

logger = logging.getLogger(__name__)


def build_generate_tab():
    """Build the Generate tab content with unified creation interface."""
    with ui.column().classes("w-full gap-4 p-4"):
        # Mode toggles
        with ui.card().classes("w-full"):
            with ui.row().classes("gap-8 items-center"):
                with ui.row().classes("items-center gap-2"):
                    mode_switch = ui.switch(
                        "Rework Mode",
                        value=APP.session_state.get("generate_mode") == "Rework",
                    ).props("color=primary")
                    mode_switch._props["marker"] = "generate-mode-toggle"
                    with ui.icon("info", size="xs").classes(
                        "text-gray-400 cursor-help"
                    ):
                        ui.tooltip(
                            "Enable to generate a new image as modification of an existing one."
                        )

                with ui.row().classes("items-center gap-2"):
                    type_switch = ui.switch(
                        "Character Sheet",
                        value=APP.session_state.get("generate_type")
                        == "Character Sheet",
                    ).props("color=secondary")
                    type_switch._props["marker"] = "generate-type-toggle"
                    with ui.icon("info", size="xs").classes(
                        "text-gray-400 cursor-help"
                    ):
                        ui.tooltip(
                            "Enable to generate a character reference sheet. Disable to generate a story page."
                        )

                resolution_select = (
                    ui.select(
                        ["1K", "2K", "4K"],
                        value=APP.session_state.get("generate_resolution", "4K"),
                        label="Resolution",
                    )
                    .classes("w-32")
                    .props("outlined dense")
                )
                resolution_select._props["marker"] = "generate-resolution-select"

                with ui.row().classes("items-center gap-1"):
                    p_threshold_input = (
                        ui.number(
                            "Top-P",
                            value=APP.settings.p_threshold if APP.settings else 0.95,
                            min=0.0,
                            max=1.0,
                            step=0.05,
                            format="%.2f",
                        )
                        .classes("w-28")
                        .props("outlined dense")
                    )
                    with ui.icon("info", size="xs").classes(
                        "text-gray-400 cursor-help"
                    ):
                        ui.tooltip(
                            "Lower values make output more focused and predictable; higher values allow more variety. Allowed values are between 0.0 and 1.0. Usually leave this near the default (0.95) and tune Temperature first."
                        )

                with ui.row().classes("items-center gap-1"):
                    temperature_input = (
                        ui.number(
                            "Temperature",
                            value=APP.settings.temperature if APP.settings else 1.0,
                            min=0.0,
                            max=2.0,
                            step=0.1,
                            format="%.1f",
                        )
                        .classes("w-28")
                        .props("outlined dense")
                    )
                    with ui.icon("info", size="xs").classes(
                        "text-gray-400 cursor-help"
                    ):
                        ui.tooltip(
                            "Controls creativity: Higher values make output more random/creative. This deteremines how wild the model behaves. Allowed values are between 0.0 and 2.0. Experiment with this first before using Top-P."
                        )

        # Rework source selection (only visible in Rework mode)
        rework_section = ui.column().classes("w-full")
        rework_source_path: list[Optional[Path]] = [None]

        def build_rework_source_selector():
            rework_section.clear()
            with rework_section:
                if not mode_switch.value:
                    return

                with ui.card().classes("w-full"):
                    ui.label("Select Image to Rework").classes("text-lg font-bold")
                    ui.label(
                        "Warning: Frequent minor reworks through the AI model can cause the image quality to deteriorate. Recommended tacctics: (i) Recreate the image with a new prompt and the original references. (ii) Fundamentally change the image composition during the rework. (iii) Remove individual objects through an external app such as the Windows Photo Editor. (iv) Remove an element of the image with an external app such as the Windows Photo Editor and then re-add it with a new prompt."
                    ).classes("text-orange-400 text-sm mb-2")
                    ui.label("Choose the original image you want to modify.").classes(
                        "text-gray-600 text-sm mb-4"
                    )

                    if not APP.project_manager or not APP.settings:
                        ui.label("Please configure settings first.").classes(
                            "text-gray-500 text-sm"
                        )
                        return

                    # Get images based on type
                    category = "references" if type_switch.value else "pages"
                    images = APP.project_manager.get_images(category)

                    if not images:
                        ui.label(f"No {category} available to rework.").classes(
                            "text-gray-500 text-sm"
                        )
                        return

                    rework_grid = ui.element("div").classes("grid grid-cols-4 gap-2")

                    with rework_grid:
                        for img in images:
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
                                    is_selected = rework_source_path[0] == full_path

                                    with ui.card().classes(
                                        "cursor-pointer p-1 hover:shadow-md transition-shadow"
                                    ) as card:
                                        if is_selected:
                                            card.style("border: 2px solid #10b981;")
                                        else:
                                            card.style("border: 2px solid transparent;")

                                        with ui.element("div").classes(
                                            "w-full h-20 bg-gray-100 flex items-center justify-center rounded"
                                        ):
                                            ui.image(str(display_path)).props(
                                                "fit=contain"
                                            ).classes("w-full h-full")
                                        ui.label(img_name[:15]).classes(
                                            "text-xs truncate text-center"
                                        )

                                        def select_rework(card=card, path=full_path):
                                            rework_source_path[0] = path
                                            APP.session_state[
                                                "selected_rework_image"
                                            ] = path
                                            build_rework_source_selector()

                                        card.on("click", select_rework)

        # Reference selection state
        selected_references: dict[str, bool] = dict(
            APP.session_state.get("selected_references", {})
        )

        # Prompt input
        with ui.card().classes("w-full"):
            ui.label("Prompt").classes("text-lg font-bold")

            with ui.expansion("System Prompt", icon="settings_system_daydream").classes(
                "w-full mb-2 bg-gray-50 rounded"
            ):
                system_prompt_display = ui.label("").classes(
                    "text-sm text-gray-600 p-2 font-mono whitespace-pre-wrap break-words"
                )

            description_input = (
                ui.textarea(
                    "Prompt",
                    value=APP.session_state.get("generate_prompt", ""),
                    placeholder="Describe what you want to create or how to modify the image...",
                )
                .classes("w-full")
                .props("outlined rows=3")
            )
            description_input._props["marker"] = "generate-prompt-input"

            # Save prompt to session state on change
            def save_prompt():
                APP.session_state["generate_prompt"] = description_input.value

            description_input.on("blur", save_prompt)

            # Selected references display
            selected_refs_container = ui.row().classes("w-full gap-2 mt-2")

            def update_selected_refs_display():
                selected_refs_container.clear()
                if not APP.project_manager:
                    return

                selected_ids = [
                    rid for rid, selected in selected_references.items() if selected
                ]
                if not selected_ids:
                    return

                # Fetch all images to find names
                all_imgs = []
                for cat in ["references", "inputs", "pages"]:
                    all_imgs.extend(APP.project_manager.get_images(cat))

                id_to_name = {
                    img["id"]: img.get("name", Path(img["path"]).stem)
                    for img in all_imgs
                }

                with selected_refs_container:
                    for rid in selected_ids:
                        name = id_to_name.get(rid, "Unknown")
                        ui.chip(name, icon="image", removable=True).on(
                            "remove", lambda e, rid=rid: remove_ref(rid)
                        )

            def remove_ref(rid):
                selected_references[rid] = False
                APP.session_state["selected_references"] = selected_references
                update_selected_refs_display()
                build_refs_grid()

        # Reference selection
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Select References").classes("text-lg font-bold")
                show_all_types = ui.switch("Show pages and inputs", value=False).props(
                    "dense"
                )

            refs_grid = ui.element("div").classes("w-full")

            def build_refs_grid():
                refs_grid.clear()
                with refs_grid:
                    if not APP.project_manager or not APP.settings:
                        ui.label("Configure settings first.").classes(
                            "text-gray-500 text-sm"
                        )
                        return

                    # Show references, inputs, and pages
                    references = APP.project_manager.get_images("references")
                    if show_all_types.value:
                        inputs = APP.project_manager.get_images("inputs")
                        pages = APP.project_manager.get_images("pages")
                        all_refs = references + inputs + pages
                    else:
                        all_refs = references

                    if not all_refs:
                        ui.label("No images available.").classes(
                            "text-gray-500 text-sm"
                        )
                        return

                    with ui.element("div").classes("grid grid-cols-6 gap-2 mt-2"):
                        for ref in all_refs:
                            ref_id = ref.get("id")
                            ref_path = ref.get("path")
                            ref_name = ref.get(
                                "name", Path(ref_path).stem if ref_path else "Unknown"
                            )

                            if ref_path:
                                full_path = Path(ref_path)
                                if not full_path.is_absolute():
                                    full_path = APP.settings.working_folder / full_path

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
                                    if ref_id not in selected_references:
                                        selected_references[ref_id] = False

                                    with ui.card().classes(
                                        "cursor-pointer p-1 hover:shadow-md transition-shadow"
                                    ) as card:
                                        if selected_references.get(ref_id, False):
                                            card.style("border: 2px solid #6366f1;")
                                        else:
                                            card.style("border: 2px solid transparent;")

                                        with ui.element("div").classes(
                                            "w-full h-16 bg-gray-100 flex items-center justify-center rounded"
                                        ):
                                            ui.image(str(display_path)).props(
                                                "fit=contain"
                                            ).classes("w-full h-full")
                                        ui.label(ref_name[:10]).classes(
                                            "text-xs truncate text-center"
                                        )

                                        def toggle_ref(card=card, rid=ref_id):
                                            selected_references[
                                                rid
                                            ] = not selected_references.get(rid, False)
                                            APP.session_state["selected_references"] = (
                                                selected_references
                                            )
                                            if selected_references[rid]:
                                                card.style("border: 2px solid #6366f1;")
                                            else:
                                                card.style(
                                                    "border: 2px solid transparent;"
                                                )
                                            update_selected_refs_display()

                                        card.on("click", toggle_ref)

            build_refs_grid()
            update_selected_refs_display()
            show_all_types.on("update:model-value", build_refs_grid)

            ui.button("↻ Refresh", on_click=build_refs_grid).props(
                "flat dense"
            ).classes("mt-2")

        # Action buttons
        with ui.row().classes("gap-2 mt-4"):

            async def generate():
                if not APP.image_service:
                    notify_error("Please configure settings first!")
                    return

                prompt = (description_input.value or "").strip()
                if not prompt:
                    ui.notify("Please enter a description!", type="warning")
                    return

                if len(prompt) > 8000:
                    ui.notify(
                        "Description is too long (max 8000 characters).", type="warning"
                    )
                    return

                mode = "Rework" if mode_switch.value else "Create"
                gen_type = "Character Sheet" if type_switch.value else "Page"
                category = "references" if gen_type == "Character Sheet" else "pages"
                system_key = (
                    "character_sheet" if gen_type == "Character Sheet" else "page"
                )
                resolution = resolution_select.value or "4K"

                # Determine aspect ratio
                aspect_ratio = "3:4"
                if APP.settings:
                    if gen_type == "Character Sheet":
                        aspect_ratio = (
                            APP.settings.character_sheet_aspect_ratio
                            or APP.settings.aspect_ratio
                        )
                    else:
                        aspect_ratio = APP.settings.aspect_ratio

                # Collect selected references
                reference_images = []
                if APP.project_manager and APP.settings:
                    # Check all image categories for selected references
                    for cat in ["references", "inputs", "pages"]:
                        images = APP.project_manager.get_images(cat)
                        for img in images:
                            if selected_references.get(img.get("id"), False):
                                img_path = img.get("path")
                                if img_path:
                                    full_path = Path(img_path)
                                    if not full_path.is_absolute():
                                        full_path = (
                                            APP.settings.working_folder / full_path
                                        )
                                    if full_path.exists():
                                        reference_images.append(full_path)

                try:
                    if mode == "Create":
                        # Create new image
                        ui.notify(f"Generating {gen_type.lower()}...", type="info")

                        if APP.status_footer:
                            async with APP.status_footer.busy(
                                f"Generating {gen_type.lower()}..."
                            ) as token:
                                (
                                    image_path,
                                    thumb_path,
                                ) = await APP.image_service.generate_image(
                                    prompt=prompt,
                                    reference_images=reference_images
                                    if reference_images
                                    else None,
                                    style_prompt=APP.settings.style_prompt
                                    if APP.settings
                                    else "",
                                    aspect_ratio=aspect_ratio,
                                    image_size=resolution,
                                    category=category,
                                    system_prompt_key=system_key,
                                    p_threshold=p_threshold_input.value,
                                    temperature=temperature_input.value,
                                    progress_callback=lambda m: APP.status_footer.update(
                                        m, token=token
                                    ),
                                )
                        else:
                            (
                                image_path,
                                thumb_path,
                            ) = await APP.image_service.generate_image(
                                prompt=prompt,
                                reference_images=reference_images
                                if reference_images
                                else None,
                                style_prompt=APP.settings.style_prompt
                                if APP.settings
                                else "",
                                aspect_ratio=aspect_ratio,
                                image_size=resolution,
                                category=category,
                                system_prompt_key=system_key,
                                p_threshold=p_threshold_input.value,
                                temperature=temperature_input.value,
                            )
                    else:
                        # Rework existing image
                        if not rework_source_path[0]:
                            ui.notify(
                                "Please select an image to rework!", type="warning"
                            )
                            return

                        ui.notify(f"Reworking {gen_type.lower()}...", type="info")

                        if APP.status_footer:
                            async with APP.status_footer.busy(
                                f"Reworking {gen_type.lower()}..."
                            ) as token:
                                (
                                    image_path,
                                    thumb_path,
                                ) = await APP.image_service.rework_image(
                                    original_image=rework_source_path[0],
                                    prompt=prompt,
                                    additional_references=reference_images
                                    if reference_images
                                    else None,
                                    style_prompt=APP.settings.style_prompt
                                    if APP.settings
                                    else "",
                                    aspect_ratio=aspect_ratio,
                                    image_size=resolution,
                                    category=category,
                                    p_threshold=p_threshold_input.value,
                                    temperature=temperature_input.value,
                                    progress_callback=lambda m: APP.status_footer.update(
                                        m, token=token
                                    ),
                                )
                        else:
                            (
                                image_path,
                                thumb_path,
                            ) = await APP.image_service.rework_image(
                                original_image=rework_source_path[0],
                                prompt=prompt,
                                additional_references=reference_images
                                if reference_images
                                else None,
                                style_prompt=APP.settings.style_prompt
                                if APP.settings
                                else "",
                                aspect_ratio=aspect_ratio,
                                image_size=resolution,
                                category=category,
                                p_threshold=p_threshold_input.value,
                                temperature=temperature_input.value,
                            )

                    ui.notify(f"{gen_type} created: {image_path.name}", type="positive")

                    # if APP.project_manager:
                    #     APP.project_manager.add_image(image_path, category, prompt[:50] if gen_type == 'Character Sheet' else None)

                    if APP.image_manager:
                        APP.image_manager.refresh()

                except ImageGenerationError as e:
                    notify_error(f"Generation failed: {e}", e)
                except Exception as e:
                    logger.exception("Unexpected error during generation")
                    notify_error(f"Unexpected error: {e}", e)

            generate_btn = ui.button(
                "Generate", on_click=generate, icon="auto_awesome"
            ).props("color=primary")
            generate_btn._props["marker"] = "generate-btn"

        # Update UI when mode changes
        def update_system_prompt_display():
            gen_type = "Character Sheet" if type_switch.value else "Page"
            system_key = "character_sheet" if gen_type == "Character Sheet" else "page"
            # If rework mode, keys are different
            if mode_switch.value:
                system_key = "rework_page" if gen_type == "Page" else "rework_character"

            # Check for project-specific override first, then fall back to default
            if APP.settings:
                override = APP.settings.get_system_prompt_override(system_key)
                if override:
                    prompt_text = override
                else:
                    prompt_text = SYSTEM_PROMPTS.get(
                        system_key, "No system prompt found."
                    )
            else:
                prompt_text = SYSTEM_PROMPTS.get(system_key, "No system prompt found.")

            # Add style prompt to display
            if APP.settings and APP.settings.style_prompt:
                style_prefix = TEMPLATES.get("style_prefix", "Style: {style_prompt}")
                formatted_style = style_prefix.format(
                    style_prompt=APP.settings.style_prompt
                )
                prompt_text += "\n\n" + formatted_style

            system_prompt_display.text = prompt_text

        def on_mode_change():
            APP.session_state["generate_mode"] = (
                "Rework" if mode_switch.value else "Create"
            )
            build_rework_source_selector()
            update_system_prompt_display()

        def on_type_change():
            APP.session_state["generate_type"] = (
                "Character Sheet" if type_switch.value else "Page"
            )
            if mode_switch.value:
                rework_source_path[0] = None
                APP.session_state["selected_rework_image"] = None
                build_rework_source_selector()
            update_system_prompt_display()

        def on_resolution_change():
            APP.session_state["generate_resolution"] = resolution_select.value

        def on_p_threshold_change():
            if APP.settings:
                APP.settings.p_threshold = p_threshold_input.value

        def on_temperature_change():
            if APP.settings:
                APP.settings.temperature = temperature_input.value

        mode_switch.on("update:model-value", on_mode_change)
        type_switch.on("update:model-value", on_type_change)
        resolution_select.on("update:model-value", on_resolution_change)
        p_threshold_input.on("change", on_p_threshold_change)
        temperature_input.on("change", on_temperature_change)

        # Initial build of rework section
        build_rework_source_selector()
        update_system_prompt_display()

        # Register refresh callbacks
        APP.register_refresh_callback(build_rework_source_selector)
        APP.register_refresh_callback(build_refs_grid)
