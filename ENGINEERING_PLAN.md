# Engineering Plan: Interactive Chat Interface

## Overview
Implement an interactive chat interface allowing users to "talk" to the codebase. Users can ask questions about the project, request explanations, or brainstorm ideas using the configured AI backend and context management system, without triggering a full coding workflow.

## Goals
- **CLI**: `agent-pump ask <query>` command.
- **TUI**: Interactive Chat Panel/Screen.
- **Context**: Smartly load relevant project context using `ContextManager`.
- **Backend**: Reuse existing `Backend` infrastructure (Gemini, Claude, etc.).

## Implementation Steps

### 1. Core Chat Service
**File**: `src/agent_pump/services/chat_service.py`

Create a `ChatService` that orchestrates the interaction:
- Accepts a query and project path.
- Uses `ContextManager` to retrieve relevant file snippets.
- Constructs a prompt for the backend (Question + Context).
- Streams the response from the backend.
- Manages chat history (transient or persisted).

**Key Methods**:
- `chat(query: str, project_path: Path, history: list[Message]) -> AsyncIterator[str]`

### 2. Backend Extension (If needed)
Check if current `Backend` classes support streaming for pure chat (non-yolo mode).
- Ensure `generate_response` or similar exists for simple text generation (not just diffs).
- Most backends currently optimize for "Plan" or "Implement". We might need a "Chat" mode/prompt.

**Prompt Template**: `src/agent_pump/prompts/chat.md` (or similar)
- System prompt: "You are an expert software engineer helper..."

### 3. CLI Integration
**File**: `src/agent_pump/cli.py`

Add `ask` command:
```bash
uv run agent-pump ask "Explain the workflow state machine"
```
- Should stream output to stdout.

### 4. TUI Integration
**File**: `src/agent_pump/tui/screens/chat_screen.py`

Create a `ChatScreen` (or `ChatModal`):
- **Layout**:
    - Top/Center: `RichLog` or `ScrollView` for message history (User: ..., Agent: ...).
    - Bottom: `Input` for typing messages.
- **Interaction**:
    - User types -> Enter.
    - Message appended to log.
    - Spinner shows while waiting.
    - Agent response streams in.

**Keybinding**:
- Add `?` or `C` (Shift+C) to open Chat.

### 5. Event Bus Updates
Define `ChatEvent` or similar if we want to decouple TUI from Service via events (optional for simple Request/Response, but good for consistency).

## Technical Details

### Context Strategy
Re-use `ContextManager.get_context_for_phase`.
Maybe define a pseudo-phase "chatting" to configure context rules (e.g., include more docs, less strict token limits).

### Streaming
The `Backend` protocol might need a `stream_response` method if not present.
If streaming is too complex for step 1, buffered response is acceptable, but TUI spinner is required.

## Testing Strategy
1. **Unit Tests**: Test `ChatService` mocking the backend.
2. **Integration Tests**: CLI `ask` command (mocked backend).
3. **TUI Tests**: Test `ChatScreen` input and display.

## Files to Modify/Create
1. Create `src/agent_pump/services/chat_service.py`
2. Modify `src/agent_pump/cli.py`
3. Create `src/agent_pump/tui/screens/chat_screen.py`
4. Modify `src/agent_pump/tui/app.py` (register screen/binding)
5. Modify `src/agent_pump/keybindings.py`
6. Create `tests/unit/test_chat_service.py`