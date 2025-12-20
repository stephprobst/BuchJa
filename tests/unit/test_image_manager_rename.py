import pytest
from pathlib import Path
from src.components.image_manager import ProjectManager

class TestProjectManagerRename:
    @pytest.fixture
    def project_manager(self, tmp_path):
        # Create a dummy project structure
        (tmp_path / "pages").mkdir()
        (tmp_path / "references").mkdir()
        (tmp_path / ".thumbnails").mkdir()
        return ProjectManager(tmp_path)

    def test_rename_image_simple(self, project_manager, tmp_path):
        # Setup: Create a source file in references
        source_file = tmp_path / "source.png"
        source_file.touch()
        
        # Add to project manager
        item = project_manager.add_image(source_file, "references", "test_ref")
        image_id = item['id']
        
        # Create a thumbnail
        target_path = tmp_path / image_id
        thumb_path = tmp_path / ".thumbnails" / f"{target_path.stem}_thumb.png"
        thumb_path.touch()
        
        # Action: Rename
        result = project_manager.rename_image(image_id, "renamed_ref")
        
        # Assert
        assert result is True
        
        # Check old files are gone
        assert not target_path.exists()
        assert not thumb_path.exists()
        
        # Check new files exist
        new_path = tmp_path / "references" / "renamed_ref.png"
        new_thumb_path = tmp_path / ".thumbnails" / "renamed_ref_thumb.png"
        
        assert new_path.exists()
        assert new_thumb_path.exists()

    def test_rename_image_pages_preserves_prefix(self, project_manager, tmp_path):
        # Setup: Create a source file in pages
        source_file = tmp_path / "source.png"
        source_file.touch()
        
        # Add to project manager (will get 001_ prefix)
        item = project_manager.add_image(source_file, "pages", "test_page")
        image_id = item['id']
        
        # Verify initial name has prefix
        assert "001_test_page" in image_id
        
        target_path = tmp_path / image_id
        thumb_path = tmp_path / ".thumbnails" / f"{target_path.stem}_thumb.png"
        thumb_path.touch()
        
        # Action: Rename (providing only the name part)
        result = project_manager.rename_image(image_id, "renamed_page")
        
        # Assert
        assert result is True
        
        # Check old files are gone
        assert not target_path.exists()
        assert not thumb_path.exists()
        
        # Check new files exist with prefix
        new_path = tmp_path / "pages" / "001_renamed_page.png"
        new_thumb_path = tmp_path / ".thumbnails" / "001_renamed_page_thumb.png"
        
        assert new_path.exists()
        assert new_thumb_path.exists()

    def test_rename_image_conflict(self, project_manager, tmp_path):
        # Setup: Create two files
        f1 = tmp_path / "f1.png"
        f1.touch()
        f2 = tmp_path / "f2.png"
        f2.touch()
        
        item1 = project_manager.add_image(f1, "references", "ref1")
        item2 = project_manager.add_image(f2, "references", "ref2")
        
        # Action: Rename ref1 to ref2
        result = project_manager.rename_image(item1['id'], "ref2")
        
        # Assert
        assert result is False
        
        # Verify files are unchanged
        assert (tmp_path / item1['id']).exists()
        assert (tmp_path / item2['id']).exists()
