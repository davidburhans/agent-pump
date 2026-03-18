# Engineering Plan: Branch Protection Rules Sync

## Overview

Implement GitHub branch protection rules synchronization to ensure Agent Pump respects repository branch protection before attempting merges.

## Requirements (from ROADMAP.md)

1. Read repository branch protection configuration from GitHub API
2. Respect required reviewers, status checks, and merge requirements  
3. Wait for all required checks to pass before attempting merge
4. Display missing requirements in workflow status

## Current State

- BranchProtectionConfig model exists with fields: `required_status_checks`, `enforce_admins`, `required_pull_request_reviews`, etc.
- BranchProtectionInfo model exists with current state info
- BranchProtectionResult model exists for operation results
- No service methods to read/validate branch protection from GitHub API

## Implementation Steps

### Step 1: Add Branch Protection Methods to GitHubService

**File**: `src/agent_pump/services/github_service.py`

Add the following methods:

```python
async def get_branch_protection(self, branch_name: str) -> BranchProtectionInfo | None:
    """Get current branch protection configuration from GitHub."""

async def check_compliance(
    self, 
    branch_name: str,
    required_config: BranchProtectionConfig
) -> BranchProtectionResult:
    """Check if branch meets required protection settings."""

async def wait_for_required_checks(
    self, 
    branch_name: str,
    timeout: int = 300
) -> bool:
    """Wait for all required status checks to pass."""
```

### Step 2: Integrate Branch Protection into Workflow

**File**: `src/agent_pump/orchestrator/workflow.py`

Update `_attempt_merge` method to:
1. Check if target branch has protection enabled
2. If protected, wait for required checks or fail gracefully  
3. Display missing requirements in workflow status

### Step 3: Add Unit Tests

**File**: `tests/unit/services/test_github_service_branch_protection.py`

Test cases:
- Read branch protection from GitHub (protected/unprotected)
- Check compliance with config
- Handle missing branch protection gracefully
- Timeout waiting for checks

## Code Implementation

### New Methods in GitHubService

```python
from github import BranchProtection

async def get_branch_protection(
    self, branch_name: str
) -> BranchProtectionInfo | None:
    """Get current branch protection configuration from GitHub.
    
    Args:
        branch_name: Name of the branch to check
        
    Returns:
        BranchProtectionInfo with current settings, or None if not protected
    """
    try:
        repo = self.get_repo()
        
        # Try to get branch (may fail for non-existent branches)
        try:
            branch = repo.get_branch(branch_name)
        except UnknownObjectException:
            logger.warning(f"Branch {branch_name} not found")
            return None
        
        # Check if protected
        protection = branch.protection
        if protection is None:
            return BranchProtectionInfo(
                branch_name=branch_name,
                is_protected=False,
            )
        
        # Extract protection settings
        required_status_checks = [
            check.context for check in protection.required_status_checks
        ] if hasattr(protection, 'required_status_checks') else []
        
        required_reviewers = []
        if hasattr(protection, 'required_pull_request_reviews'):
            review = protection.required_pull_request_reviews
            if review and hasattr(review, 'dismissal_restrictions'):
                required_reviewers = [
                    user.login for user in review.dismissal_restrictions.users
                ]
        
        return BranchProtectionInfo(
            branch_name=branch_name,
            is_protected=True,
            required_status_checks=required_status_checks or None,
            enforce_admins=bool(getattr(protection, 'enforce_admins', False)),
            required_pull_request_reviews=required_reviewers or None,
            dismiss_stale_reviews=getattr(protection, 'dismiss_stale_reviews', True),
            require_code_owner_reviews=getattr(protection, 'require_code_owner_reviews', False),
            required_approving_review_count=getattr(
                protection, 'required_approving_review_count', 1
            ),
            allow_force_pushes=getattr(protection, 'allow_force_pushes', False),
            allow_deletions=getattr(protection, 'allow_deletions', False),
        )
        
    except (GithubException, RateLimitExceededException) as e:
        logger.error(f"Failed to get branch protection for {branch_name}: {e}")
        return None
```

### Compliance Check Method

```python
async def check_compliance(
    self, 
    branch_name: str,
    required_config: BranchProtectionConfig
) -> BranchProtectionResult:
    """Check if branch meets required protection settings.
    
    Args:
        branch_name: Name of the branch to check
        required_config: Required configuration
        
    Returns:
        BranchProtectionResult with compliance status and missing requirements
    """
    current = await self.get_branch_protection(branch_name)
    
    if current is None:
        return BranchProtectionResult(
            success=False,
            branch_name=branch_name,
            error="Branch not found or could not be read",
        )
    
    missing_requirements = []
    
    # Check required status checks
    if (
        required_config.required_status_checks
        and not current.required_status_checks
    ):
        missing_requirements.append("required_status_checks")
    
    # Check enforce admins
    if (
        required_config.enforce_admins
        and not current.enforce_admins
    ):
        missing_requirements.append("enforce_admins")
    
    # Check required reviewers
    if (
        required_config.required_pull_request_reviews
        and not current.required_pull_request_reviews
    ):
        missing_requirements.append("required_pull_request_reviews")
    
    return BranchProtectionResult(
        success=len(missing_requirements) == 0,
        branch_name=branch_name,
        is_protected=current.is_protected,
        error=None if len(missing_requirements) == 0 else "Missing requirements",
        missing_requirements=missing_requirements,
    )
```

### Wait for Checks Method

```python
async def wait_for_required_checks(
    self, 
    branch_name: str,
    timeout: int = 300
) -> bool:
    """Wait for all required status checks to pass.
    
    Polls GitHub API every 10 seconds until checks complete or timeout.
    
    Args:
        branch_name: Name of the branch to check
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if checks passed, False on timeout or error
    """
    import asyncio
    
    start_time = asyncio.get_event_loop().time()
    poll_interval = 10
    
    try:
        repo = self.get_repo()
        branch = repo.get_branch(branch_name)
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for status checks on {branch_name}")
                return False
            
            # Get commit status
            head_sha = branch.commit.sha
            combined_status = repo.get_commit(head_sha).get_combined_status()
            
            # Check if all required contexts passed
            if combined_status.state == "success":
                logger.info(f"All status checks passed for {branch_name}")
                return True
            
            if combined_status.state in ("error", "failure"):
                logger.error(f"Status checks failed for {branch_name}: {combined_status.state}")
                return False
            
            # Wait before polling again
            await asyncio.sleep(poll_interval)
            
    except (GithubException, RateLimitExceededException) as e:
        logger.error(f"Error checking status on {branch_name}: {e}")
        return False
```

### Update Merge Logic in Workflow

```python
async def _attempt_merge(self) -> MergeResult:
    """Attempt to merge the feature branch into the base branch.
    
    Checks branch protection before attempting merge.
    """
    from agent_pump.services.branch_manager import BranchManager, MergeResult
    
    # ... existing branch manager code ...
    
    # NEW: Check branch protection if configured
    if self.project_config and self.project_config.github_integration:
        github_config = self.project_config.github_integration
        
        if hasattr(github_config, 'branch_protection_config') and github_config.branch_protection_config:
            protection_config = github_config.branch_protection_config
            
            if protection_config.enabled:  # Add this field to BranchProtectionConfig
                self._emit_output(
                    f"\n[BRANCH PROTECTION] Checking {self.branch_config.base_branch}...\n"
                )
                
                # Check compliance
                result = await self.github_service.check_compliance(
                    self.branch_config.base_branch,
                    protection_config
                )
                
                if not result.success:
                    self._emit_output(
                        f"\n[BRANCH PROTECTION] Missing requirements: "
                        f"{', '.join(result.missing_requirements)}\n"
                    )
                    
                    if protection_config.fail_on_missing_protection:
                        return MergeResult(
                            success=False,
                            has_conflicts=False,
                            error=f"Missing branch protection requirements: {result.missing_requirements}",
                        )
                    
                    # Wait for required checks
                    self._emit_output("[BRANCH PROTECTION] Waiting for required checks...\n")
                    checks_passed = await self.github_service.wait_for_required_checks(
                        self.branch_config.base_branch,
                        timeout=protection_config.check_timeout or 300
                    )
                    
                    if not checks_passed:
                        return MergeResult(
                            success=False,
                            has_conflicts=False,
                            error="Required status checks did not pass within timeout",
                        )
    
    # Continue with existing merge logic...
```

## Testing

### Unit Tests

```python
@pytest.mark.asyncio
async def test_get_branch_protection_protected():
    """Test getting protection for a protected branch."""
    mock_repo = MagicMock()
    mock_branch = MagicMock()
    mock_protection = MagicMock()
    
    # Mock the protection object structure
    mock_protection.required_status_checks = [
        MagicMock(context="ci/circleci"),
        MagicMock(context="security/scan"),
    ]
    mock_protection.enforce_admins = True
    mock_protection.dismiss_stale_reviews = True
    mock_protection.require_code_owner_reviews = False
    mock_protection.required_approving_review_count = 2
    
    mock_branch.protection = mock_protection
    mock_repo.get_branch.return_value = mock_branch
    
    service = GitHubService(config)
    service._client = MagicMock()
    
    result = await service.get_branch_protection("main")
    
    assert result.is_protected is True
    assert "ci/circleci" in result.required_status_checks
    assert result.enforce_admins is True

@pytest.mark.asyncio  
async def test_check_compliance_missing_requirements():
    """Test checking compliance when requirements are missing."""
    required = BranchProtectionConfig(
        required_status_checks=["ci/circleci"],
        enforce_admins=True,
    )
    
    current = BranchProtectionInfo(
        branch_name="main",
        is_protected=False,
    )
    
    result = await service.check_compliance("main", required)
    
    assert result.success is False
    assert "required_status_checks" in result.missing_requirements

@pytest.mark.asyncio
async def test_wait_for_required_checks_timeout():
    """Test timeout waiting for status checks."""
    # Mock combined status to always return pending
    mock_commit = MagicMock()
    mock_status = MagicMock()
    mock_status.state = "pending"
    mock_commit.get_combined_status.return_value = mock_status
    
    mock_repo = MagicMock()
    mock_branch = MagicMock()
    mock_branch.commit.sha = "abc123"
    mock_repo.get_branch.return_value = mock_branch
    mock_repo.get_commit.return_value = mock_commit
    
    service = GitHubService(config)
    
    result = await service.wait_for_required_checks("main", timeout=5)
    
    assert result is False  # Timeout
```

## Summary

This implementation adds comprehensive branch protection support to Agent Pump, ensuring that automated merges respect GitHub repository protection rules. The workflow will:
1. Check if target branch has protection enabled
2. Verify required settings are configured
3. Wait for status checks to pass before merging
4. Display clear error messages when requirements are missing
