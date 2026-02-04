"""Templates package for agent-pump."""

from agent_pump.templates.builtin import (
    get_all_builtin_templates,
    get_builtin_template,
    get_go_template,
    get_node_npm_template,
    get_python_uv_template,
    get_rust_cargo_template,
)

__all__ = [
    "get_all_builtin_templates",
    "get_builtin_template",
    "get_go_template",
    "get_node_npm_template",
    "get_python_uv_template",
    "get_rust_cargo_template",
]
