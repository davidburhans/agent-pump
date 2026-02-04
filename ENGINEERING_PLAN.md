# Engineering Plan: Bootstrap TUI Integration

## Overview
Add TUI integration for the Project Bootstrap feature, allowing users to bootstrap projects directly from the TUI dashboard instead of only via CLI.

## Current State
- Bootstrap service is fully implemented (`src/agent_pump/services/bootstrap_service.py`)
- CLI integration is complete (`src/agent_pump/cli.py`)
- TUI integration is missing (FEATURES.md line 1103)

## Implementation Steps

### 1. Create BootstrapModal Component
**File**: `src/agent_pump/tui/screens/bootstrap_modal.py`

**Features**:
- Directory selection (DirectoryTree widget)
- Backend selection dropdown (Gemini, Claude, Qwen, OpenCode)
- Dry-run toggle checkbox
- Project analysis preview before bootstrapping
- Success/failure feedback

**UI Layout**:
- Title: "Bootstrap Project"
- Directory tree for path selection
- Backend selector (dropdown)
- Dry-run checkbox
- Preview panel showing detected project type
- Action buttons: Cancel, Preview, Bootstrap

### 2. Add Keybinding
**File**: `src/agent_pump/keybindings.py`

Add new keybinding:
- Key: `B` (shift+b, since `b` is used for backend config)
- Action: `bootstrap_project`
- Description: "Bootstrap"
- Scope: global

### 3. Integrate with TUI App
**File**: `src/agent_pump/tui/app.py`

Add:
- Import BootstrapModal
- `action_bootstrap_project()` method
- Handler for modal result that calls BootstrapService
- Progress/status updates during bootstrap

### 4. Export Modal
**File**: `src/agent_pump/tui/screens/__init__.py`

Add export for BootstrapModal.

### 5. Write Unit Tests
**File**: `tests/unit/test_bootstrap_modal.py`

**Test Coverage**:
- Modal composition and widgets
- Directory selection handling
- Backend selection
- Dry-run toggle
- Validation of project path
- Error handling (invalid path, bootstrap failure)
- Success path with mock bootstrap service

### 6. Update Documentation
**Files**: 
- `FEATURES.md`: Update audit status for Bootstrap feature from 🟡 to ✅
- `ROADMAP.md`: Mark as complete and move to FEATURES.md

## Technical Details

### Modal Return Type
```python
BootstrapResult = tuple[Path, str, bool] | None  # (path, backend, dry_run) or None if cancelled
```

### Integration with BootstrapService
```python
async def _bootstrap_project(self, path: Path, backend: str, dry_run: bool) -> None:
    service = BootstrapService(self.event_bus)
    result = await service.bootstrap_project(
        project_path=path,
        backend=backend,
        dry_run=dry_run
    )
    if result.success:
        self.notify(f"Bootstrapped {path.name}: {len(result.files_written)} files created")
    else:
        self.notify(f"Bootstrap failed: {result.error_message}", severity="error")
```

## Testing Strategy

1. **Unit Tests**: Mock BootstrapService, test UI interactions
2. **Integration**: Test with actual directory selection
3. **Error Cases**: Invalid paths, service failures
4. **Success Cases**: Complete bootstrap flow

## Files to Modify
1. Create: `src/agent_pump/tui/screens/bootstrap_modal.py` (~200 lines)
2. Modify: `src/agent_pump/keybindings.py` (+8 lines)
3. Modify: `src/agent_pump/tui/screens/__init__.py` (+1 line)
4. Modify: `src/agent_pump/tui/app.py` (+30 lines)
5. Create: `tests/unit/test_bootstrap_modal.py` (~150 lines)
6. Modify: `FEATURES.md` (update audit status)
7. Modify: `ROADMAP.md` (mark complete)

## Acceptance Criteria
- [ ] Press `B` in TUI opens Bootstrap modal
- [ ] Can select project directory via DirectoryTree
- [ ] Can choose backend from dropdown
- [ ] Can enable/disable dry-run mode
- [ ] Shows preview of detected project type
- [ ] Successfully bootstraps project on confirmation
- [ ] Shows appropriate success/error notifications
- [ ] All unit tests pass
- [ ] Linting and type checking pass
