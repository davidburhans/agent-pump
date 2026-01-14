# Engineering Plan: Real-time State Visibility

## Goal
Enhance the user experience by providing real-time feedback on what the agent is currently doing (e.g., "Reading file...", "Running command...", "Thinking..."). This involves parsing the agent's output stream for activity indicators and displaying this granular status in the TUI Project Card.

## detailed Tasks

### 1. Workflow & State Enhancements
- [x] Add `current_activity` field to `WorkflowState` model (string, nullable) to persist the last known detailed activity.
- [x] Add `current_activity` field to `Project` model (string, nullable) for in-memory tracking.
- [x] Update `ProjectWorkflow` to parse backend output lines for activity indicators.
    - [x] Identify patterns for tool calls (e.g., "Running tool:", "Calling tool:", "read_file", etc.).
    - [x] Update `current_activity` when these patterns are matched.
    - [x] Clear `current_activity` when phase changes or after a timeout/completion.
- [x] Expose `on_activity_change` callback in `ProjectWorkflow`.

### 2. TUI Updates
- [x] Update `ProjectCard` widget to subscribe to activity updates.
- [x] Add a visual element (e.g., a sub-label) to `ProjectCard` to display `current_activity`.
- [x] Style the activity text (e.g., dim/italic) to distinguish it from the main status.
- [x] Ensure activity text is truncated if too long.

### 3. Backend Output Parsing Strategy
- [x] Analyze typical output from Gemini/Claude/OpenCode backends to identify common patterns for tool usage.
    - Gemini: Often prints `Running tool: ...` or similar.
    - Claude Code: Prints `> command` or similar.
    - OpenCode: Similar patterns.
- [x] Implement a regex-based or string-matching parser in `ProjectWorkflow` (or a helper class) to extract the "verb" and "target" (e.g., "Reading file X").

### 4. Verification & Polish
- [x] Verify that `current_activity` updates in real-time as the agent runs.
- [x] Ensure the UI doesn't flicker too much with rapid updates.
- [x] Verify persistence: `current_activity` doesn't strictly need to be persisted to disk for long-term storage, but `WorkflowState` updates should probably include it if we want it to survive a quick restart, though it's mostly transient. Let's decide to keep it transient in `Project` model for now, as it's only relevant while running.
- [x] Update tests to ensure parsing logic works.

### 5. Finalize
- [x] Reflect on work and update BEST_PRACTICES.md.