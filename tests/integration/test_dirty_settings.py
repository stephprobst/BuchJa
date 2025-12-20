"""Integration tests for dirty settings warning.

Tests that a warning modal appears when navigating away from unsaved settings.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from nicegui import ui
from nicegui.testing import User

@pytest.fixture
def mock_services(mock_keyring, temp_dir):
    """Mock all services for integration tests."""
    mock_kr, _ = mock_keyring
    with patch('src.services.settings.keyring', mock_kr), \
         patch('src.services.settings.Settings') as MockSettings:
        
        # Create a real-ish Settings instance
        settings_instance = MagicMock()
        settings_instance.get_api_key.return_value = ""
        settings_instance.working_folder = temp_dir
        settings_instance.aspect_ratio = "3:4"
        settings_instance.style_prompt = ""
        
        MockSettings.return_value = settings_instance
        
        yield settings_instance

@pytest.mark.integration
@pytest.mark.asyncio
class TestDirtySettings:
    """Tests for dirty settings warning."""

    async def test_dirty_warning_appears(self, user: User, mock_services):
        """Test that warning appears when settings are modified and tab is changed."""
        await user.open('/')
        
        # 1. Go to Settings tab
        user.find('Settings').click()
        await asyncio.sleep(1.0)
        await user.should_see('API Configuration')
        
        # 2. Modify a setting (API Key)
        # Use ui.input to find the input.
        user.find(ui.input).type('new-api-key')
        
        # Wait a bit for value to update
        await asyncio.sleep(1.0)
        
        # 3. Try to navigate to another tab (e.g. 'Crop')
        # 'Add' might match text in instructions, 'Crop' is hopefully more unique or finds the tab.
        user.find('Crop').click()
        await asyncio.sleep(1.0)
        
        # 4. Verify Dialog appears
        await user.should_see('You have unsaved settings. Do you really want to leave?')
        
        # 5. Click 'Stay'
        user.find('Stay').click()
        
        # Should still be on Settings tab (API Configuration visible)
        await user.should_see('API Configuration')
        # And dialog should be gone (or closing)
        
        # 6. Try to navigate again
        user.find('Add').click()
        await user.should_see('You have unsaved settings. Do you really want to leave?')
        
        # 7. Click 'Leave'
        user.find('Leave').click()
        
        # Should now be on Add tab
        await user.should_see('Upload Reference Images')

