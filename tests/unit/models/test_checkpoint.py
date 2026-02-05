"""Tests for checkpoint model."""

from datetime import datetime
from typing import cast

from agent_pump.models.checkpoint import Checkpoint, CheckpointCollection


class TestCheckpoint:
    """Tests for Checkpoint model."""

    def test_default_creation(self):
        """Test checkpoint creation with defaults."""
        checkpoint = Checkpoint(
            phase="planning",
            git_commit_hash="abc123def456",
            description="Before planning phase",
        )

        assert checkpoint.phase == "planning"
        assert checkpoint.git_commit_hash == "abc123def456"
        assert checkpoint.description == "Before planning phase"
        assert checkpoint.auto_created is True
        assert checkpoint.feature is None
        assert len(checkpoint.id) == 8  # Short UUID
        assert isinstance(checkpoint.timestamp, datetime)
        assert checkpoint.files_modified == []

    def test_manual_checkpoint(self):
        """Test manual checkpoint creation."""
        checkpoint = Checkpoint(
            phase="implementing",
            git_commit_hash="xyz789abc123",
            description="Manual save point",
            auto_created=False,
            feature="Add login page",
        )

        assert checkpoint.auto_created is False
        assert checkpoint.feature == "Add login page"
        assert checkpoint.phase == "implementing"

    def test_with_files_modified(self):
        """Test checkpoint with modified files list."""
        files = ["src/main.py", "tests/test_main.py", "README.md"]
        checkpoint = Checkpoint(
            phase="verifying",
            git_commit_hash="def789abc123",
            description="Before verification",
            files_modified=files,
        )

        assert checkpoint.files_modified == files

    def test_to_dict(self):
        """Test conversion to dictionary."""
        checkpoint = Checkpoint(
            id="chk12345",
            phase="planning",
            git_commit_hash="abc123",
            description="Test checkpoint",
            auto_created=True,
        )

        data = checkpoint.to_dict()

        assert data["id"] == "chk12345"
        assert data["phase"] == "planning"
        assert data["git_commit_hash"] == "abc123"
        assert data["description"] == "Test checkpoint"
        assert data["auto_created"] is True
        assert isinstance(data["timestamp"], datetime)

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "chk67890",
            "timestamp": datetime.now(),
            "phase": "implementing",
            "feature": "Feature X",
            "git_commit_hash": "xyz789",
            "description": "From dict test",
            "files_modified": ["file1.py", "file2.py"],
            "auto_created": False,
        }

        checkpoint = Checkpoint.from_dict(data)

        assert checkpoint.id == "chk67890"
        assert checkpoint.phase == "implementing"
        assert checkpoint.feature == "Feature X"
        assert checkpoint.git_commit_hash == "xyz789"
        assert checkpoint.auto_created is False

    def test_get_short_hash(self):
        """Test short hash extraction."""
        checkpoint = Checkpoint(
            phase="planning",
            git_commit_hash="abcdef1234567890abcdef1234567890abcdef12",
            description="Test",
        )

        assert checkpoint.get_short_hash() == "abcdef1"

    def test_get_formatted_time(self):
        """Test formatted timestamp."""
        now = datetime(2024, 1, 15, 10, 30, 0)
        checkpoint = Checkpoint(
            phase="planning",
            git_commit_hash="abc123",
            description="Test",
            timestamp=now,
        )

        assert checkpoint.get_formatted_time() == "2024-01-15 10:30:00"

    def test_str_representation_auto(self):
        """Test string representation for auto checkpoint."""
        checkpoint = Checkpoint(
            id="abc123",
            phase="planning",
            git_commit_hash="def789",
            description="Before planning",
            auto_created=True,
        )

        result = str(checkpoint)
        assert "Checkpoint abc123 [auto]" in result
        assert "Before planning" in result
        assert "def789" in result

    def test_str_representation_manual(self):
        """Test string representation for manual checkpoint."""
        checkpoint = Checkpoint(
            id="xyz789",
            phase="implementing",
            git_commit_hash="abc123",
            description="Manual save",
            auto_created=False,
        )

        result = str(checkpoint)
        assert "Checkpoint xyz789 [manual]" in result
        assert "Manual save" in result


class TestCheckpointCollection:
    """Tests for CheckpointCollection."""

    def test_empty_collection(self):
        """Test empty checkpoint collection."""
        collection = CheckpointCollection()

        assert len(collection) == 0
        assert collection.get_latest() is None
        assert collection.list_all() == []
        assert collection.get_by_id("nonexistent") is None

    def test_add_checkpoint(self):
        """Test adding checkpoint to collection."""
        collection = CheckpointCollection()
        checkpoint = Checkpoint(
            phase="planning",
            git_commit_hash="abc123",
            description="Test checkpoint",
        )

        collection.add(checkpoint)

        assert len(collection) == 1
        assert collection.get_latest() == checkpoint

    def test_add_multiple_checkpoints(self):
        """Test adding multiple checkpoints."""
        collection = CheckpointCollection()

        for i in range(3):
            checkpoint = Checkpoint(
                id=f"chk{i}",
                phase="planning",
                git_commit_hash=f"hash{i}",
                description=f"Checkpoint {i}",
            )
            collection.add(checkpoint)

        assert len(collection) == 3
        latest = collection.get_latest()
        assert latest.id == "chk2"
        assert latest.description == "Checkpoint 2"

    def test_get_by_id(self):
        """Test retrieving checkpoint by ID."""
        collection = CheckpointCollection()
        checkpoint1 = Checkpoint(
            id="find-me",
            phase="planning",
            git_commit_hash="abc123",
            description="Target checkpoint",
        )
        checkpoint2 = Checkpoint(
            id="other",
            phase="implementing",
            git_commit_hash="def456",
            description="Other checkpoint",
        )

        collection.add(checkpoint1)
        collection.add(checkpoint2)

        found = collection.get_by_id("find-me")
        assert found is not None
        assert found.id == "find-me"
        assert found.description == "Target checkpoint"

        not_found = collection.get_by_id("nonexistent")
        assert not_found is None

    def test_list_all(self):
        """Test listing all checkpoints."""
        collection = CheckpointCollection()
        checkpoints = [
            Checkpoint(phase="planning", git_commit_hash="a", description="First"),
            Checkpoint(phase="implementing", git_commit_hash="b", description="Second"),
            Checkpoint(phase="verifying", git_commit_hash="c", description="Third"),
        ]

        for cp in checkpoints:
            collection.add(cp)

        result = collection.list_all()
        assert len(result) == 3
        assert result[0].description == "First"
        assert result[1].description == "Second"
        assert result[2].description == "Third"

    def test_remove_by_id(self):
        """Test removing checkpoint by ID."""
        collection = CheckpointCollection()
        checkpoint = Checkpoint(
            id="remove-me",
            phase="planning",
            git_commit_hash="abc123",
            description="To be removed",
        )

        collection.add(checkpoint)
        assert len(collection) == 1

        removed = collection.remove_by_id("remove-me")
        assert removed is True
        assert len(collection) == 0

        not_removed = collection.remove_by_id("nonexistent")
        assert not_removed is False

    def test_clear(self):
        """Test clearing all checkpoints."""
        collection = CheckpointCollection()

        for i in range(5):
            collection.add(
                Checkpoint(
                    phase="planning",
                    git_commit_hash=f"hash{i}",
                    description=f"Checkpoint {i}",
                )
            )

        assert len(collection) == 5
        collection.clear()
        assert len(collection) == 0
        assert collection.list_all() == []

    def test_max_checkpoints_limit(self):
        """Test that collection respects max checkpoint limit."""
        collection = CheckpointCollection()
        collection.MAX_CHECKPOINTS = 10  # Set lower for testing

        # Add more than max
        for i in range(15):
            collection.add(
                Checkpoint(
                    phase="planning",
                    git_commit_hash=f"hash{i}",
                    description=f"Checkpoint {i}",
                )
            )

        # Should be trimmed to max
        assert len(collection) == 10
        # Oldest should be removed (first 5 trimmed)
        assert collection.list_all()[0].description == "Checkpoint 5"

    def test_checkpoint_order_preserved(self):
        """Test that checkpoint order is preserved chronologically."""
        collection = CheckpointCollection()

        cp1 = Checkpoint(
            id="first",
            phase="planning",
            git_commit_hash="abc",
            description="First",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
        )
        cp2 = Checkpoint(
            id="second",
            phase="implementing",
            git_commit_hash="def",
            description="Second",
            timestamp=datetime(2024, 1, 1, 11, 0, 0),
        )

        collection.add(cp1)
        collection.add(cp2)

        checkpoints = collection.list_all()
        cp1 = cast(Checkpoint, checkpoints[0])
        assert cp1.id == "first"
        cp2 = cast(Checkpoint, checkpoints[1])
        assert cp2.id == "second"
