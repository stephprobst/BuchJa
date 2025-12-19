import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.components.image_manager import ProjectManager

class TestProjectManager:
    @pytest.fixture
    def project_manager(self, tmp_path):
        # Create a dummy project structure
        (tmp_path / "pages").mkdir()
        (tmp_path / ".thumbnails").mkdir()
        return ProjectManager(tmp_path)

    def test_remove_image_deletes_file(self, project_manager, tmp_path):
        # Setup: Create a source file
        source_file = tmp_path / "source.png"
        source_file.touch()
        
        # Add to project manager
        item = project_manager.add_image(source_file, "pages", "test_image")
        image_id = item['id']
        
        # The file in pages/ should exist
        target_path = tmp_path / image_id
        assert target_path.exists()
        
        # Create a thumbnail for the target file
        target_stem = target_path.stem
        thumb_path = tmp_path / ".thumbnails" / f"{target_stem}_thumb.png"
        thumb_path.touch()
        
        assert thumb_path.exists()
        
        # Action: Remove the image
        result = project_manager.remove_image(image_id)
        
        # Assert
        assert result is True
        assert not target_path.exists(), "Image file should be deleted"
        assert not thumb_path.exists(), "Thumbnail file should be deleted"
        
        # Verify it's gone from the project data
        images = project_manager.get_images("pages")
        assert len(images) == 0

    def test_remove_image_handles_missing_file(self, project_manager, tmp_path):
        # Action: Remove a non-existent image
        result = project_manager.remove_image("pages/ghost_image.png")
        
        # Assert
        assert result is False
