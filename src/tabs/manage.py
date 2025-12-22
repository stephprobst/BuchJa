from nicegui import ui
from src.app import APP
from src.components.image_manager import ImageManager

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
                    current_tab = 'Pages'
                    if APP.image_manager and hasattr(APP.image_manager, '_current_tab'):
                        current_tab = APP.image_manager._current_tab

                    with manager_container:
                        manager_container.clear()
                        APP.image_manager = ImageManager(
                            project_manager=APP.project_manager,
                            working_folder=APP.settings.working_folder,
                            image_service=APP.image_service,
                            initial_tab=current_tab
                        )
            
            init_manager()
            APP.register_refresh_callback(init_manager)
            with ui.row().classes('gap-2'):
                ui.button('Refresh', on_click=init_manager, icon='refresh').props('outline')
                ui.button('OPEN IN FILE EXPLORER', on_click=lambda: APP.image_manager.open_current_folder() if APP.image_manager else None, icon='folder_open').props('outline')
