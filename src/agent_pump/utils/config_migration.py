"""Migration helper for configuration."""

from pathlib import Path


class ConfigMigrator:
    """Migrate legacy .agent-pump.yml to directory structure."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.legacy_file = project_path / ".agent-pump.yml"
        self.new_dir = project_path / ".agent-pump"

    def needs_migration(self) -> bool:
        """Check if legacy config exists without new directory."""
        # Check if legacy exists AND (new dir doesn't exist OR new config doesn't exist)
        # But wait, if new dir exists but config doesn't, we should probably migrate.
        has_legacy = self.legacy_file.exists()
        has_new_config = (self.new_dir / "config.yml").exists()
        return has_legacy and not has_new_config

    def migrate(self, remove_legacy: bool = False) -> None:
        """Convert legacy config to directory structure.

        Args:
            remove_legacy: If True, delete .agent-pump.yml after migration
        """
        if not self.legacy_file.exists():
            return

        # Create directory structure
        (self.new_dir / "states").mkdir(parents=True, exist_ok=True)
        (self.new_dir / "backends").mkdir(parents=True, exist_ok=True)

        # Move config
        legacy_content = self.legacy_file.read_text(encoding="utf-8")
        (self.new_dir / "config.yml").write_text(legacy_content, encoding="utf-8")

        # Create stub prompt files with instructions
        for state in [
            "planning",
            "implementing",
            "verifying",
            "brainstorming",
            "committing",
        ]:
            stub = self.new_dir / "states" / f"pre-{state}.md"
            if not stub.exists():
                stub.write_text(
                    f"<!-- Add custom instructions to prepend to {state} phase -->\n",
                    encoding="utf-8",
                )

        if remove_legacy:
            self.legacy_file.unlink()
