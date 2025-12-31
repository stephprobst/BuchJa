from nicegui import ui


def tip(text: str):
    with ui.row().classes("items-center gap-2 mt-4"):
        ui.label("Tips:").classes("font-bold text-gray-600")
        with ui.icon("lightbulb").classes("text-yellow-500 cursor-help"):
            ui.tooltip(text).classes("bg-gray-600 text-white text-body2 p-2")


def markdown_tip(text: str):
    with ui.row().classes("items-center gap-2 mt-4"):
        ui.label("Tips:").classes("font-bold text-gray-600")
        with ui.icon("lightbulb").classes("text-yellow-500 cursor-help"):
            with ui.tooltip().classes("bg-gray-600 text-white text-body2 p-2"):
                ui.markdown(text)


def build_instructions_tab():
    """Build the Instructions tab content."""
    with ui.column().classes("w-full gap-6 p-4 max-w-4xl"):
        with ui.card().classes("w-full"):
            ui.label("Welcome to BuchJa").classes("text-2xl font-bold mb-4")
            ui.label(
                "This application helps you create illustrated books using AI. Follow the steps below to get started."
            ).classes("text-gray-700 mb-4")

        with ui.card().classes("w-full"):
            ui.label("1. Setup").classes("text-xl font-bold mb-2")
            ui.markdown("""
            - Go to the **Settings** tab.
            - Enter your **Gemini API Key**. This is securely stored in the System Keyring.
            - Select a **Working Folder** for your project files and generated images.
            - Choose an **Aspect Ratio** for book pages (and optionally a different one for character sheets).
            - Enter a **Style Prompt** to define the artistic style.
            """).classes("text-gray-700")
            markdown_tip("""
            - Ask an AI chatbot for a one-sentence description of your favorite book or illustrator's style.
            - Keep the style prompt concise (< 20 words) to avoid the AI from focusing too much on style over content.
            """)

        with ui.card().classes("w-full"):
            ui.label("2. Add Input References").classes("text-xl font-bold mb-2")
            ui.markdown("""
            Skip this step if you don't need personalized characters or specific objects.

            - Go to the **Add** tab.
            - Upload reference photos or images for inspiration. These will be saved to the `Inputs` folder in your working directory.
            """).classes("text-gray-700")
            tip(
                "You can also copy and paste images directly into the working folder using File Explorer."
            )

        with ui.card().classes("w-full"):
            ui.label("3. Create Character Sheets").classes("text-xl font-bold mb-2")
            ui.markdown("""
            - Go to the **Generate** tab.
            - Enable the **Character Sheet** toggle at the top. Creating character sheets first helps maintain consistency.
            - Select your uploaded reference images to guide the character design.
            - Experiment with prompts and settings until you are satisfied with the character designs.
            """).classes("text-gray-700")
            markdown_tip("""
            - Start with 1k resolution for faster, cheaper generation. Upscale later if needed.
            - Don't recreate the same page too often with minor changes. For some reason the image quality degrades a tiny bit each time.
            - If you base your characters on real people, make the clothing match something they commonly wear. This helps a lot with recognizability.
            """)

        with ui.card().classes("w-full"):
            ui.label("4. Generate Pages").classes("text-xl font-bold mb-2")
            ui.markdown("""
            - Go to the **Generate** tab.
            - Select reference images (ensure all characters appearing in the scene are selected).
            - Enter a prompt describing the scene.
            """).classes("text-gray-700")

            markdown_tip("""
            - Use external tools (PowerPoint, Canva, etc.) for text layout later, but don't forget to leave whitespace for it.
            - Use the **Sketch** tab to draw simple stick figures for composition control and attach them as references.
            - Use the **Crop** tab to save elements from generated pages to reuse as references in following pages. This is important for maintaining consistency.
            - Keep the character count per page low (max. 3-4 people) for better coherence.
            """)

        with ui.card().classes("w-full"):
            ui.label("5. Manage & Export").classes("text-xl font-bold mb-2")
            ui.markdown("""
            - Go to the **Manage** tab to review, rename, and reorder your pages and characters.
            - You can reclassify images as pages, references, or inputs.
            - Use the **Export** tab to create a PDF, or copy images directly from the working folder for use in other layout software.       
            """).classes("text-gray-700")
            tip(
                "You can also open images in an external image editor and edit them there further, e.g. by removing individual objects. This can sometimes work better than regenerating the entire image."
            )
