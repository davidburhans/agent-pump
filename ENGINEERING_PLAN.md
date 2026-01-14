# Engineering Plan: Feature Prioritization

## Goal
Allow users to view and reorder uncompleted roadmap items via the TUI. This ensures the agent works on tasks in the order preferred by the user.

## Detailed Tasks

### 1. Roadmap Parsing & Serialization
- [x] Create a utility to parse `ROADMAP.md` into a structured list of features.
    - Identify `🔴 Not Started` items in "Future Enhancements" and "Current Sprint".
    - Capture description and acceptance criteria.
- [x] Create a utility to update `ROADMAP.md` with a new order of items.
    - Preserves formatting, completed items, and status legend.

### 2. TUI Components
- [x] Create `RoadmapScreen` (ModalScreen) to display the list of uncompleted items.
- [x] Implement `RoadmapItem` widget or use `ListItem` for the list.
- [x] Add keyboard bindings to `RoadmapScreen`:
    - `k`/`j` or `up`/`down` to select item.
    - `K`/`J` or `ctrl+up`/`ctrl+down` to move selected item up/down.
    - `Enter` to save and exit.
    - `Esc` to cancel.
- [x] Add a global binding `m` (for "Manage Roadmap") to `AgentPumpApp` to open the screen.

### 3. Orchestrator Integration
- [x] Update `ProjectWorkflow` (or the logic that picks the next task) to respect the order of `ROADMAP.md`.
    - (Wait, currently the agent is triggered manually or by a task loop. If it's the "Agent Pump" orchestrator, it should pick the first `🔴 Not Started` item).
- [x] Ensure that when `ROADMAP.md` is updated, any running or pending task selection reflects the new first item.

### 4. Verification
- [x] Add unit tests for roadmap parsing and reordering.
- [x] Verify TUI interaction: items move correctly and state is saved.
- [x] Verify that the orchestrator picks the new top item after reordering.

### 5. Finalize
- [x] Update `ROADMAP.md` status to `🟢 Complete`.
- [x] Update `BEST_PRACTICES.md` with lessons learned.
