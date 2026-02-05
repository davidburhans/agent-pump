# Engineering Plan - Automated Web UI Build Command

This plan focuses on completing and refining the automated build process for the Web UI, ensuring it is production-ready, well-documented, and thoroughly tested.

## Goals
- Provide a robust CLI command for building the React frontend.
- Improve user experience by streaming build output.
- Ensure the build process is integrated into the project's documentation.
- Verify the build output is correctly served by the FastAPI backend via integration tests.

## Tasks

### Implementation
- [x] Refactor `run_ui_build` in `src/agent_pump/utils/ui_build.py` to stream subprocess output.
    - [x] Use `subprocess.Popen` instead of `subprocess.run` to read lines in real-time.
    - [x] Print `npm install` and `npm run build` output to the console as it happens.
- [x] Ensure `ui` command group and `build` command are correctly registered in `src/agent_pump/cli.py`.
- [x] Add comprehensive error handling for common build failures (e.g., node missing, network errors during install).

### Testing
- [x] Update `tests/unit/test_cli_ui.py` to reflect streaming output changes.
- [x] Add a new integration test `tests/integration/test_ui_build_cli.py` that mocks the build process and verifies CLI integration.
- [x] Verify `tests/integration/test_web_ui.py` passes after a successful UI build.

### Documentation
- [x] Update `README.md` to include the `agent-pump ui build` command group and usage.
- [x] Update `ROADMAP.md` to mark "Automated Web UI Build Command" as completed (✅).
- [x] Update `FEATURES.md` to reflect the final implementation status and audit.

### Finalization
- [x] Verify that `agent-pump --web` correctly serves the UI assets after a fresh build.
- [x] Reflect on the work done and update BEST_PRACTICES.md with any lessons learned, and check if README.md needs updates as a result.