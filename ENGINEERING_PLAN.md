# Engineering Plan: OpenCode API Backend

## Objective
Implement a new backend `OpenCodeAPIBackend` that uses the `opencode-ai` SDK to interact with OpenCode. This replaces or supplements the existing CLI-based backend, providing better programmatic control, improved exception handling, and better reliability.

## Current State
- `OpenCodeBackend` in `src/agent_pump/backends/opencode.py` uses `subprocess` to call the `opencode` CLI.
- `opencode-ai` SDK is already included in `pyproject.toml`.

## Proposed Changes

### 1. New Backend Class
Create `src/agent_pump/backends/opencode_api.py` containing `OpenCodeAPIBackend`.

- **Name**: "OpenCode API"
- **Internal ID**: "opencode-api"
- **SDK**: Use `opencode_ai.AsyncOpencode`.
- **Base URL**: Default to `http://localhost:54321` (OpenCode default) or `OPENCODE_BASE_URL` env var.
- **Availability**: Available if the local OpenCode server is reachable or SDK is importable (depending on preferred check). We'll check if we can connect to the base URL.

### 2. Workflow Integration
- Use `client.session.init` to start a session.
- Use `client.session.chat` to send prompts.
- Implement streaming support using `client.with_streaming_response.session.chat`.

### 3. Error Handling
- Use SDK-specific exceptions (`APIError`, `APITimeoutError`, etc.) for robust error reporting and retries.

### 4. Registry Update
- Register the new backend in `src/agent_pump/backends/__init__.py`.

## Tasks

### Implementation
- [ ] Create `src/agent_pump/backends/opencode_api.py`.
- [ ] Implement `OpenCodeAPIBackend._check_availability` to verify server connectivity.
- [ ] Implement `OpenCodeAPIBackend.run` with `AsyncOpencode` and streaming.
- [ ] Add `OpenCodeAPIBackend` to `BACKEND_REGISTRY` in `src/agent_pump/backends/__init__.py`.
- [ ] Ensure `extra_args` (like `--model`) are passed correctly to the SDK calls.

### Testing
- [ ] Create `tests/unit/test_opencode_api.py`.
- [ ] Mock `AsyncOpencode` and its session resources to test:
    - Successful chat and streaming.
    - Error handling (e.g., connection refused, timeout).
    - Availability check.

### Documentation & Cleanup
- [ ] Update `ROADMAP.md` to mark the feature as in progress (🟡).
- [ ] Update `FEATURES.md` with information about the new API backend.
- [ ] Reflect on the work done and update BEST_PRACTICES.md with any lessons learned, and check if README.md needs updates as a result.