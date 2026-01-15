"""Tests for ConfigMigrator."""


import pytest

from agent_pump.utils.config_migration import ConfigMigrator


class TestConfigMigrator:
    """Tests for the ConfigMigrator class."""

    @pytest.fixture
    def project_path(self, tmp_path):
        """Create a temporary project path."""
        path = tmp_path / "test_project"
        path.mkdir()
        return path

    def test_needs_migration(self, project_path):
        """Test detection of migration need."""
        migrator = ConfigMigrator(project_path)
        assert not migrator.needs_migration()

        # Create legacy config
        (project_path / ".agent-pump.yml").touch()
        assert migrator.needs_migration()

        # Create new directory (but no config) -> Should STILL need migration
        (project_path / ".agent-pump").mkdir()
        assert migrator.needs_migration()
        
        # Create config.yml -> Should NOT need migration
        (project_path / ".agent-pump" / "config.yml").touch()
        assert not migrator.needs_migration()

    def test_migrate(self, project_path):
        """Test migration process."""
        legacy_file = project_path / ".agent-pump.yml"
        legacy_file.write_text("config: value", encoding="utf-8")

        migrator = ConfigMigrator(project_path)
        migrator.migrate(remove_legacy=False)

        new_dir = project_path / ".agent-pump"
        assert new_dir.is_dir()
        assert (new_dir / "states").is_dir()
        assert (new_dir / "backends").is_dir()
        assert (new_dir / "config.yml").read_text(encoding="utf-8") == "config: value"
        assert (new_dir / "states" / "pre-planning.md").exists()
        assert legacy_file.exists()  # Should not be removed

    def test_migrate_remove_legacy(self, project_path):
        """Test migration with legacy removal."""
        legacy_file = project_path / ".agent-pump.yml"
        legacy_file.write_text("config: value", encoding="utf-8")

        migrator = ConfigMigrator(project_path)
        migrator.migrate(remove_legacy=True)

        assert not legacy_file.exists()
        assert (project_path / ".agent-pump" / "config.yml").exists()
