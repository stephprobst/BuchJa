from nicegui import ui

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
