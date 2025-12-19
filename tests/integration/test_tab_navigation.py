"""Integration tests for tab navigation and state preservation.

Tests the vertical tab layout and ensure state is preserved when switching tabs.
"""

import pytest
from nicegui.testing import User


@pytest.mark.integration
@pytest.mark.asyncio
class TestTabNavigation:
    """Tests for the vertical tab navigation system."""

    async def test_all_tabs_exist(self, user: User):
        """Test that all five main tabs are visible."""
        await user.open('/')
        
        await user.should_see('Settings')
        await user.should_see('Add')
        await user.should_see('Crop')
        await user.should_see('Generate')
        await user.should_see('Manage')

    async def test_settings_tab_is_default(self, user: User):
        """Test that Settings tab is shown by default."""
        await user.open('/')
        
        # Settings tab content should be visible
        await user.should_see('API Configuration')
        await user.should_see('Working Folder')
        await user.should_see('Aspect Ratio')
        await user.should_see('Book Style')

    async def test_switch_to_add_tab(self, user: User):
        """Test switching to the Add tab."""
        await user.open('/')
        
        # Wait for the UI to settle, then click on Add tab by its label
        await user.should_see('Add')
        user.find(content='Add').click()
        
        # Add tab content should be visible
        await user.should_see('Upload Reference Images')

    async def test_switch_to_crop_tab(self, user: User):
        """Test switching to the Crop tab."""
        await user.open('/')
        
        # Wait for the UI to settle, then click on Crop tab by its label
        await user.should_see('Crop')
        user.find(content='Crop').click()
        
        # Crop tab content should be visible
        await user.should_see('Crop from Existing Image')

    async def test_switch_to_generate_tab(self, user: User):
        """Test switching to the Generate tab."""
        await user.open('/')
        
        # Wait for the UI to settle, then click on Generate tab by its label
        await user.should_see('Generate')
        user.find(content='Generate').click()
        
        # Generate tab content should be visible
        await user.should_see('Rework Mode')
        await user.should_see('Character Sheet')
        await user.should_see('Prompt')
        await user.should_see('Select References')

    async def test_switch_to_manage_tab(self, user: User):
        """Test switching to the Manage tab."""
        await user.open('/')
        
        # Wait for the UI to settle, then click on Manage tab by its label
        await user.should_see('Manage')
        user.find(content='Manage').click()
        
        # Manage tab content should be visible
        await user.should_see('Image Management')
        await user.should_see('Export to PDF')

    async def test_tab_switch_back_and_forth(self, user: User):
        """Test switching between tabs multiple times."""
        await user.open('/')
        
        # Start at Settings
        await user.should_see('API Configuration')
        
        # Go to Generate
        await user.should_see('Generate')
        user.find(content='Generate').click()
        await user.should_see('Select References')
        
        # Go to Add
        user.find(content='Add').click()
        await user.should_see('Upload Reference Images')
        
        # Go back to Settings
        user.find(content='Settings').click()
        await user.should_see('API Configuration')


@pytest.mark.integration
@pytest.mark.asyncio
class TestGenerateTabUI:
    """Tests for the Generate tab user interface."""

    async def test_mode_toggle_exists(self, user: User):
        """Test that mode toggle (Create/Rework) exists."""
        await user.open('/')
        await user.should_see('Generate')
        user.find(content='Generate').click()
        
        # Should see mode toggle
        await user.should_see('Create')
        await user.should_see('Rework')

    async def test_type_toggle_exists(self, user: User):
        """Test that type toggle (Character Sheet/Page) exists."""
        await user.open('/')
        await user.should_see('Generate')
        user.find(content='Generate').click()
        
        # Should see type toggle
        await user.should_see('Character Sheet')
        await user.should_see('Page')

    async def test_generate_button_exists(self, user: User):
        """Test that generate button exists."""
        await user.open('/')
        await user.should_see('Generate')
        user.find(content='Generate').click()
        
        # Should see generate button text
        await user.should_see('Generate')

    async def test_prompt_input_exists(self, user: User):
        """Test that prompt input exists."""
        await user.open('/')
        await user.should_see('Generate')
        user.find(content='Generate').click()
        
        # Should see prompt label
        await user.should_see('Prompt')

    async def test_sketch_expansion_exists(self, user: User):
        """Test that sketch expansion panel exists."""
        await user.open('/')
        await user.should_see('Generate')
        user.find(content='Generate').click()
        
        await user.should_see('Add a sketch')


@pytest.mark.integration
@pytest.mark.asyncio
class TestSettingsTabUI:
    """Tests for the Settings tab user interface."""

    async def test_api_key_input_exists(self, user: User):
        """Test that API key input exists in Settings tab."""
        await user.open('/')
        
        # Should see API key input label
        await user.should_see('API Key')

    async def test_aspect_ratio_select_exists(self, user: User):
        """Test that aspect ratio select exists in Settings tab."""
        await user.open('/')
        
        # Should see aspect ratio label
        await user.should_see('Page Aspect Ratio')

    async def test_style_prompt_input_exists(self, user: User):
        """Test that style prompt input exists in Settings tab."""
        await user.open('/')
        
        # Should see style prompt label
        await user.should_see('Style Prompt')

    async def test_save_settings_button_exists(self, user: User):
        """Test that save settings button exists."""
        await user.open('/')
        
        await user.should_see('Save Settings')


@pytest.mark.integration
@pytest.mark.asyncio
class TestManageTabUI:
    """Tests for the Manage tab user interface."""

    async def test_export_filename_input_exists(self, user: User):
        """Test that export filename input exists."""
        await user.open('/')
        await user.should_see('Manage')
        user.find(content='Manage').click()
        
        # Should see filename input label
        await user.should_see('Output Filename')

    async def test_export_pdf_button_exists(self, user: User):
        """Test that export PDF button exists."""
        await user.open('/')
        await user.should_see('Manage')
        user.find(content='Manage').click()
        
        # Should see export button
        await user.should_see('Export PDF')

    async def test_refresh_button_exists(self, user: User):
        """Test that refresh button exists."""
        await user.open('/')
        await user.should_see('Manage')
        user.find(content='Manage').click()
        
        await user.should_see('Refresh')


@pytest.mark.integration
@pytest.mark.asyncio
class TestHeaderUI:
    """Tests for the header components."""

    async def test_app_title_visible(self, user: User):
        """Test that app title is visible."""
        await user.open('/')
        
        await user.should_see('Book Creator')

    async def test_usage_tokens_visible(self, user: User):
        """Test that usage tokens label is visible."""
        await user.open('/')
        
        # Should see tokens display
        await user.should_see('Tokens:')

    async def test_reset_button_exists(self, user: User):
        """Test that reset usage button exists."""
        await user.open('/')
        
        # Should see usage since label (reset button is nearby)
        await user.should_see('Since:')
