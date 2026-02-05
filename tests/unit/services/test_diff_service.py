from pathlib import Path
from unittest.mock import patch

import pytest

from agent_pump.models.diff import DiffChangeType
from agent_pump.services.diff_service import DiffService


@pytest.fixture
def mock_repo():
    with patch("agent_pump.services.diff_service.git.Repo") as mock:
        yield mock

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
