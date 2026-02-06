from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.diff import DiffChangeType
from agent_pump.services.diff_service import DiffService


@pytest.fixture
def mock_repo():
    with patch("agent_pump.services.diff_service.git.Repo") as mock:
        yield mock


@pytest.fixture
def mock_checkpoint():
    """Create a mock checkpoint object."""
    checkpoint = MagicMock()
    checkpoint.id = "abc1234"
    checkpoint.description = "Test checkpoint"
    checkpoint.get_short_hash.return_value = "abc1234"
    return checkpoint


def test_get_staged_diffs(mock_repo):
    # Mock repo.git.diff output
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = """diff --git a/file.txt b/file.txt
index ...
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-old
+new
"""

    service = DiffService(Path("/tmp"))
    diffs = service.get_staged_diffs()

    assert len(diffs) == 1
    assert diffs[0].path == "file.txt"
    assert diffs[0].status == DiffChangeType.MODIFIED
    mock_instance.git.diff.assert_called_with("--staged", "--unified=3")


def test_get_unstaged_diffs(mock_repo):
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = ""

    service = DiffService(Path("/tmp"))
    diffs = service.get_unstaged_diffs()

    assert len(diffs) == 0
    mock_instance.git.diff.assert_called_with("--unified=3")


def test_get_checkpoint_diffs(mock_repo):
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = """diff --git a/new.txt b/new.txt
new file mode 100644
index ...
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+content
"""

    service = DiffService(Path("/tmp"))
    diffs = service.get_checkpoint_diffs("abc1234")

    assert len(diffs) == 1
    assert diffs[0].status == DiffChangeType.ADDED
    mock_instance.git.diff.assert_called_with("abc1234^", "abc1234", "--unified=3")


def test_get_available_checkpoints(mock_repo):
    """Test getting available checkpoints from git history."""
    mock_instance = mock_repo.return_value

    # Mock git log output
    mock_commit = MagicMock()
    mock_commit.hexsha = "abc1234def5678"
    mock_commit.message = "Test commit message\nMore details"
    mock_commit.committed_datetime = MagicMock()
    mock_commit.committed_datetime.strftime.return_value = "2025-02-05 10:00"

    mock_instance.iter_commits.return_value = [mock_commit]

    service = DiffService(Path("/tmp"))
    checkpoints = service.get_available_checkpoints(max_count=10)

    assert len(checkpoints) == 1
    assert checkpoints[0]["id"] == "abc1234def5678"
    assert checkpoints[0]["message"] == "Test commit message"
    mock_instance.iter_commits.assert_called_with(max_count=10)


def test_get_diffs_by_type_all(mock_repo):
    """Test getting all diffs."""
    mock_instance = mock_repo.return_value
    # When getting "all", it calls both staged and unstaged, so we need to
    # return different values for each call to verify concatenation works
    mock_instance.git.diff.side_effect = [
        # First call (staged)
        """diff --git a/staged.txt b/staged.txt
index ...
--- a/staged.txt
+++ b/staged.txt
@@ -1 +1 @@
-old
+new
""",
        # Second call (unstaged)
        """diff --git a/unstaged.txt b/unstaged.txt
index ...
--- a/unstaged.txt
+++ b/unstaged.txt
@@ -1 +1 @@
-old
+new
""",
    ]

    service = DiffService(Path("/tmp"))
    diffs = service.get_diffs_by_type("all")

    # Should have both staged and unstaged files
    assert len(diffs) == 2
    assert diffs[0].path == "staged.txt"
    assert diffs[1].path == "unstaged.txt"


def test_get_diffs_by_type_staged(mock_repo):
    """Test getting staged diffs via get_diffs_by_type."""
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = """diff --git a/staged.txt b/staged.txt
index ...
--- a/staged.txt
+++ b/staged.txt
@@ -1 +1 @@
-old
+new
"""

    service = DiffService(Path("/tmp"))
    diffs = service.get_diffs_by_type("staged")

    assert len(diffs) == 1
    assert diffs[0].path == "staged.txt"
    mock_instance.git.diff.assert_called_with("--staged", "--unified=3")


def test_get_diffs_by_type_unstaged(mock_repo):
    """Test getting unstaged diffs via get_diffs_by_type."""
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = """diff --git a/unstaged.txt b/unstaged.txt
index ...
--- a/unstaged.txt
+++ b/unstaged.txt
@@ -1 +1 @@
-old
+new
"""

    service = DiffService(Path("/tmp"))
    diffs = service.get_diffs_by_type("unstaged")

    assert len(diffs) == 1
    assert diffs[0].path == "unstaged.txt"
    mock_instance.git.diff.assert_called_with("--unified=3")


def test_get_diffs_by_type_checkpoint(mock_repo):
    """Test getting checkpoint diffs via get_diffs_by_type."""
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = """diff --git a/checkpoint.txt b/checkpoint.txt
new file mode 100644
index ...
--- /dev/null
+++ b/checkpoint.txt
@@ -0,0 +1 @@
+content
"""

    service = DiffService(Path("/tmp"))
    diffs = service.get_diffs_by_type("checkpoint", checkpoint_id="abc123")

    assert len(diffs) == 1
    mock_instance.git.diff.assert_called_with("abc123^", "abc123", "--unified=3")


def test_get_diff_statistics(mock_repo):
    """Test getting diff statistics."""
    mock_instance = mock_repo.return_value
    mock_instance.git.diff.return_value = """diff --git a/file.txt b/file.txt
index ...
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,4 @@
 line1
+added1
 line2
-old
+new
 line3
"""

    service = DiffService(Path("/tmp"))
    stats = service.get_diff_statistics()

    assert stats["files_changed"] == 1
    assert stats["additions"] == 2
    assert stats["deletions"] == 1
