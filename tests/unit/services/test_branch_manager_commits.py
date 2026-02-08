from unittest.mock import MagicMock, patch

import pytest

from agent_pump.services.branch_manager import BranchManager


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.git.log.return_value = "commit1\ncommit2"
    return repo

def test_get_branch_commits(mock_repo):
    with patch("agent_pump.services.branch_manager.Repo", return_value=mock_repo):
        bm = BranchManager("/tmp/repo")
        commits = bm.get_branch_commits("feature", "main")

        # Verify git log called with correct range
        mock_repo.git.log.assert_called_once_with("main..feature", "--pretty=format:%s")
        assert commits == ["commit1", "commit2"]

def test_get_branch_commits_empty(mock_repo):
    mock_repo.git.log.return_value = ""
    with patch("agent_pump.services.branch_manager.Repo", return_value=mock_repo):
        bm = BranchManager("/tmp/repo")
        commits = bm.get_branch_commits("feature", "main")
        assert commits == []

def test_get_branch_commits_error(mock_repo):
    from git import GitCommandError
    mock_repo.git.log.side_effect = GitCommandError("log", "error")

    with patch("agent_pump.services.branch_manager.Repo", return_value=mock_repo):
        bm = BranchManager("/tmp/repo")
        commits = bm.get_branch_commits("feature", "main")
        assert commits == []  # Should return empty list on error
