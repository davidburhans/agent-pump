# Engineering Plan: Dynamic Project Management

## Goal
Enable full runtime management of projects, allowing users to add, remove, start, and stop projects individually or collectively without restarting the application. Ensure true concurrent execution of multiple projects.

## Feature Description
Currently, the application supports adding/removing projects but lacks granular control over their execution state. The global "Pause/Resume" logic is ambiguous. We need to:
1.  Provide explicit Start/Stop controls for individual projects.
2.  Ensure "Start All" / "Stop All" work reliably.
3.  Verify that multiple projects run concurrently without blocking.
4.  Refine the TUI to reflect these capabilities.

## Implementation Plan

### Phase 1: Core Orchestration Enhancements
- [ ] Refactor `AgentPumpApp._run_project` to ensure it checks if a workflow is already running before starting.
- [ ] Implement `AgentPumpApp._stop_project(path)` to cancel a specific project's workflow.
- [ ] Update `AgentPumpApp.action_toggle_pause` to control the **selected** project only.
- [ ] Add new keybinding `S` (Shift+s) or similar to "Start Selected".
- [ ] Add new keybinding `X` (Shift+x) or similar to "Stop Selected".

### Phase 2: TUI Components
- [ ] Update `ProjectCard` to visually distinguish between "Running", "Paused", and "Idle" more clearly (e.g., border color or status text).
- [ ] Update the button row in `AgentPumpApp`:
    - [ ] "Start All" -> Iterates all projects and calls `_run_project`.
    - [ ] "Stop All" -> Iterates all workflows and calls `cancel`.
- [ ] Add "Start" and "Stop" buttons to the `ProjectCard` itself (optional, but good for mouse users)? -> *Decision: Keep it keyboard-centric for now, use global buttons for bulk actions.*

### Phase 3: Project Management Logic
- [ ] Verify `_add_project` handles duplicates gracefully (already exists).
- [ ] Verify `_remove_project` cancels the workflow before removal (already exists).
- [ ] Ensure `AppState` persistence correctly saves the list of projects on add/remove.

### Phase 4: Verification
- [ ] Create a test with multiple mock projects.
- [ ] Verify they can be started and run in parallel (checking logs/states).
- [ ] Verify removing a running project stops it and cleans up.

### Phase 5: Cleanup & Documentation
- [ ] Update `BEST_PRACTICES.md` with any new patterns (e.g., worker management).
- [ ] Update `ROADMAP.md` (mark as complete).
- [ ] Reflect on lessons learned.

## Task List

- [ ] **Refactor Start/Stop Logic**
    - [ ] Modify `src/agent_pump/tui/app.py`: Split `action_toggle_pause` into `action_start_selected` and `action_stop_selected`.
    - [ ] Implement `action_start_all` and `action_stop_all`.
    - [ ] Update key bindings: `s` for Start Selected, `x` for Stop Selected (or Pause).

- [ ] **Update TUI Layout**
    - [ ] Update `src/agent_pump/tui/app.py`: Bind buttons to new actions.
    - [ ] Update Help/Footer to show new bindings.

- [ ] **Verify Concurrency**
    - [ ] Create a manual reproduction script or integration test that adds 2 projects and starts them.

- [ ] **Reflect and Update Docs**
    - [ ] Update `BEST_PRACTICES.md`.
    - [ ] Check `README.md`.