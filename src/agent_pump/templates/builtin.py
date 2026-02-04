"""Built-in project templates for agent-pump."""

from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.template import ProjectTemplate, TemplateConfig, TemplatePrompts
from agent_pump.models.verification_config import VerificationConfig
from agent_pump.models.workspace import BackendFallback, BackendInstance, PhaseBackends


def get_python_uv_template() -> ProjectTemplate:
    """Get the Python/uv built-in template."""
    return ProjectTemplate(
        name="python-uv",
        description="Python project using uv toolchain with ruff and pytest",
        category="built-in",
        tags=["python", "uv", "ruff", "pytest"],
        author="Agent Pump",
        version="1.0.0",
        config=TemplateConfig(
            backend="gemini",
            workflow_max_iterations=10,
            workflow_timeout=1800,
            branch_strategy=BranchStrategyConfig(
                enabled=True,
                auto_create_branch=True,
                auto_merge=False,
                branch_prefix="feature",
                base_branch="main",
                require_clean_worktree=True,
                push_on_merge=False,
            ),
            verification=VerificationConfig(
                build_cmd="uv build",
                lint_cmd="uv run ruff check .",
                test_cmd="uv run pytest tests/ -v",
                skip_verification=False,
            ),
            phase_backends=PhaseBackends(
                defaults=BackendFallback(
                    backends=[BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])]
                )
            ),
            workflow_name="default",
            min_execution_time_seconds=10,
            default_timeout=1800,
        ),
        prompts=TemplatePrompts(
            pre_planning="This is a Python project using the `uv` toolchain for dependency management and packaging. Use modern Python patterns (3.12+) and type hints.\n\nKey tools:\n- uv: For dependency management and builds\n- ruff: For linting and formatting\n- pytest: For testing\n\nAlways use `uv run` to execute commands.",
            pre_implementing="When writing Python code:\n1. Use type hints for all function signatures\n2. Use `|` union syntax (Python 3.10+), not `Union`\n3. Prefer `list[str]` over `List[str]`\n4. Use `Path` from pathlib, not string paths\n5. Follow ruff's default linting rules\n6. Write pytest tests for new functionality\n7. Use Pydantic v2 for data models when appropriate",
            pre_verifying="Verify that:\n1. All code passes `uv run ruff check .`\n2. All tests pass with `uv run pytest tests/ -v`\n3. The project builds with `uv build`\n4. Type hints are complete and correct\n5. No runtime errors in the implementation",
        ),
    )


def get_node_npm_template() -> ProjectTemplate:
    """Get the Node.js/npm built-in template."""
    return ProjectTemplate(
        name="node-npm",
        description="Node.js project using npm with eslint and jest",
        category="built-in",
        tags=["nodejs", "javascript", "typescript", "npm", "jest"],
        author="Agent Pump",
        version="1.0.0",
        config=TemplateConfig(
            backend="gemini",
            workflow_max_iterations=10,
            workflow_timeout=1800,
            branch_strategy=BranchStrategyConfig(
                enabled=True,
                auto_create_branch=True,
                auto_merge=False,
                branch_prefix="feature",
                base_branch="main",
                require_clean_worktree=True,
                push_on_merge=False,
            ),
            verification=VerificationConfig(
                build_cmd="npm run build",
                lint_cmd="npm run lint",
                test_cmd="npm test",
                skip_verification=False,
            ),
            phase_backends=PhaseBackends(
                defaults=BackendFallback(
                    backends=[BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])]
                )
            ),
            workflow_name="default",
            min_execution_time_seconds=10,
            default_timeout=1800,
        ),
        prompts=TemplatePrompts(
            pre_planning="This is a Node.js project using npm for package management.\n\nKey conventions:\n- Use modern JavaScript (ES2022+) or TypeScript\n- Follow npm scripts convention (build, test, lint)\n- Use eslint for code quality\n- Use jest for testing\n\nAlways check for package.json and ensure dependencies are installed with `npm install`.",
            pre_implementing="When writing Node.js code:\n1. Use async/await for asynchronous operations\n2. Prefer const/let over var\n3. Use ES modules (import/export) when possible\n4. Follow eslint rules configured in the project\n5. Write jest tests for new functionality\n6. Handle errors gracefully with try/catch\n7. Use TypeScript for type safety when available",
            pre_verifying="Verify that:\n1. All code passes `npm run lint`\n2. All tests pass with `npm test`\n3. The project builds with `npm run build`\n4. No unhandled promise rejections\n5. All dependencies are properly declared in package.json",
        ),
    )


def get_rust_cargo_template() -> ProjectTemplate:
    """Get the Rust/cargo built-in template."""
    return ProjectTemplate(
        name="rust-cargo",
        description="Rust project using cargo with clippy for linting",
        category="built-in",
        tags=["rust", "cargo", "clippy"],
        author="Agent Pump",
        version="1.0.0",
        config=TemplateConfig(
            backend="gemini",
            workflow_max_iterations=10,
            workflow_timeout=1800,
            branch_strategy=BranchStrategyConfig(
                enabled=True,
                auto_create_branch=True,
                auto_merge=False,
                branch_prefix="feature",
                base_branch="main",
                require_clean_worktree=True,
                push_on_merge=False,
            ),
            verification=VerificationConfig(
                build_cmd="cargo build --all-targets --all-features",
                lint_cmd="cargo clippy --all-targets --all-features -- -D warnings",
                test_cmd="cargo test --all-targets --all-features",
                skip_verification=False,
            ),
            phase_backends=PhaseBackends(
                defaults=BackendFallback(
                    backends=[BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])]
                )
            ),
            workflow_name="default",
            min_execution_time_seconds=10,
            default_timeout=1800,
        ),
        prompts=TemplatePrompts(
            pre_planning="This is a Rust project using cargo for build management.\n\nKey conventions:\n- Follow Rust naming conventions (snake_case for functions, CamelCase for types)\n- Use cargo for all build/test operations\n- Use clippy for linting\n- Prefer Result/Option over panics\n- Use the type system to prevent bugs at compile time\n\nAlways check Cargo.toml and ensure the project compiles.",
            pre_implementing="When writing Rust code:\n1. Use strong typing - leverage the type system\n2. Handle errors with Result, use ? operator\n3. Avoid unwrap() and expect() in production code\n4. Use clippy warnings as a guide for idiomatic code\n5. Write unit tests in the same file (#[cfg(test)] mod tests)\n6. Use cargo doc to generate documentation\n7. Follow Rust API guidelines for public interfaces",
            pre_verifying="Verify that:\n1. Code compiles without warnings: `cargo build --all-targets --all-features`\n2. All clippy lints pass: `cargo clippy --all-targets --all-features -- -D warnings`\n3. All tests pass: `cargo test --all-targets --all-features`\n4. Documentation builds: `cargo doc`\n5. No unsafe code unless absolutely necessary (document why)\n6. Proper error handling throughout",
        ),
    )


def get_go_template() -> ProjectTemplate:
    """Get the Go built-in template."""
    return ProjectTemplate(
        name="go",
        description="Go project with standard tooling",
        category="built-in",
        tags=["go", "golang"],
        author="Agent Pump",
        version="1.0.0",
        config=TemplateConfig(
            backend="gemini",
            workflow_max_iterations=10,
            workflow_timeout=1800,
            branch_strategy=BranchStrategyConfig(
                enabled=True,
                auto_create_branch=True,
                auto_merge=False,
                branch_prefix="feature",
                base_branch="main",
                require_clean_worktree=True,
                push_on_merge=False,
            ),
            verification=VerificationConfig(
                build_cmd="go build ./...",
                lint_cmd="golangci-lint run ./...",
                test_cmd="go test ./... -v",
                skip_verification=False,
            ),
            phase_backends=PhaseBackends(
                defaults=BackendFallback(
                    backends=[BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])]
                )
            ),
            workflow_name="default",
            min_execution_time_seconds=10,
            default_timeout=1800,
        ),
        prompts=TemplatePrompts(
            pre_planning="This is a Go project.\n\nKey conventions:\n- Follow standard Go formatting (gofmt)\n- Use go modules for dependency management\n- Use golangci-lint for comprehensive linting\n- Follow Go naming conventions (CamelCase for exported, camelCase for internal)\n- Keep interfaces small and focused\n\nAlways check go.mod and ensure dependencies are tidy.",
            pre_implementing="When writing Go code:\n1. Use gofmt for consistent formatting\n2. Handle errors explicitly - never ignore errors\n3. Use defer for resource cleanup\n4. Write table-driven tests\n5. Use interfaces to define behavior\n6. Keep functions small and focused\n7. Document exported functions and types",
            pre_verifying="Verify that:\n1. Code is formatted: `gofmt -l .` returns nothing\n2. All tests pass: `go test ./... -v`\n3. Project builds: `go build ./...`\n4. Linting passes: `golangci-lint run ./...`\n5. Dependencies are tidy: `go mod tidy`\n6. No race conditions: `go test -race ./...`",
        ),
    )


def get_all_builtin_templates() -> list[ProjectTemplate]:
    """Get all built-in templates."""
    return [
        get_python_uv_template(),
        get_node_npm_template(),
        get_rust_cargo_template(),
        get_go_template(),
    ]


def get_builtin_template(name: str) -> ProjectTemplate | None:
    """Get a specific built-in template by name."""
    templates = {t.name: t for t in get_all_builtin_templates()}
    return templates.get(name)
