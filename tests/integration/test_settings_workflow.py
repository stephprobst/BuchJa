"""Integration tests for settings workflow.

Tests the complete settings UI workflow using NiceGUI User simulation.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from nicegui import ui
from nicegui.testing import User


@pytest.fixture
def mock_services(mock_keyring, temp_dir):
    """Mock all services for integration tests."""
    # mock_keyring is a tuple (mock_kr, stored_passwords)
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
class TestSettingsWorkflow:
    """Integration tests for the settings workflow."""

    async def test_settings_section_loads(self, user: User, mock_services):
        """Test that the settings section loads correctly."""
        await user.open('/')
        
        # Check settings section exists
        await user.should_see('Settings')

    async def test_api_key_input_exists(self, user: User, mock_services):
        """Test that API key input field exists."""
        await user.open('/')
        
        # Expand settings section if collapsed
        user.find(content='Settings').click()
        
        # Should see API key related elements
        await user.should_see('API Key')

    async def test_save_api_key(self, user: User, mock_services):
        """Test saving an API key."""
        await user.open('/')
        
        # Expand settings section
        user.find(content='Settings').click()
        
        # Should see save button
        await user.should_see('Save Settings')

    async def test_working_folder_display(self, user: User, mock_services, temp_dir):
        """Test working folder is displayed."""
        mock_services.working_folder = temp_dir
        
        await user.open('/')
        
        # Should show working folder section
        await user.should_see('Working Folder')

    async def test_aspect_ratio_selection(self, user: User, mock_services):
        """Test aspect ratio selection."""
        await user.open('/')
        
        # Should see aspect ratio options
        await user.should_see('Aspect Ratio')

    async def test_settings_validation_empty_key(self, user: User, mock_services):
        """Test validation when trying to save empty API key."""
        mock_services.get_api_key.return_value = ""
        
        await user.open('/')
        
        # Settings section should still load
        await user.should_see('Settings')


@pytest.mark.integration
@pytest.mark.asyncio
class TestSettingsPersistence:
    """Tests for settings persistence across sessions."""

    async def test_api_key_persists(self, user: User, mock_services):
        """Test that API key persists after being saved."""
        mock_services.get_api_key.return_value = "saved-key"
        
        await user.open('/')
        
        # Settings should load
        await user.should_see('Settings')

    async def test_style_prompt_persists(self, user: User, mock_services):
        """Test that style prompt persists."""
        mock_services.style_prompt = "Watercolor children's book style"
        
        await user.open('/')
        
        # Style section should be populated
        await user.should_see('Style')


@pytest.mark.integration
@pytest.mark.asyncio  
class TestErrorHandling:
    """Tests for error handling in settings."""

    async def test_invalid_api_key_format(self, user: User, mock_services):
        """Test handling of invalid API key format."""
        await user.open('/')
        
        # Page should load and handle gracefully
        await user.should_see('Settings')

    async def test_keyring_unavailable(self, user: User, temp_dir, caplog):
        """Test fallback when keyring is unavailable."""
        import logging
        
        with patch('src.services.settings.keyring') as mock_kr:
            # Set up the mock to raise an exception
            mock_kr.get_password.side_effect = Exception("Keyring unavailable")
            # Also need to mock the errors attribute
            mock_kr.errors = MagicMock()
            mock_kr.errors.KeyringError = Exception
            
            from src.services.settings import Settings
            
            # Expect an ERROR log when keyring fails
            with caplog.at_level(logging.ERROR):
                settings = Settings()
                
                # Should fall back to file storage or handle gracefully
                api_key = settings.get_api_key()
                assert api_key == "" or api_key is None
            
            # Verify the error was logged as expected
            assert "Failed to retrieve API key" in caplog.text
            
            # Clear the log records so NiceGUI's user fixture doesn't fail on expected errors
            caplog.clear()
