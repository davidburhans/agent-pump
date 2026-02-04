"""Keybinding definitions for Agent Pump.

This module acts as the single source of truth for keyboard shortcuts,
shared between the TUI and the Web Dashboard.
"""

from typing import Literal

from pydantic import BaseModel


class Keybinding(BaseModel):
    """Model for a keyboard shortcut."""

    key: str
    action: str
    description: str
    web_available: bool = True
    show_in_footer: bool = True
    scope: Literal["global", "project"] = "global"


KEYBINDINGS: list[Keybinding] = [
    # Global Bindings (Always available)
    Keybinding(
        key="ctrl+p",
        action="command_palette",
        description="Cmds",
        scope="global",
    ),
    Keybinding(
        key="a",
        action="add_project",
        description="Add",
        scope="global",
    ),
    Keybinding(
        key="i",
        action="add_idea",
        description="Idea",
        scope="global",
    ),
    Keybinding(
        key="m",
        action="manage_roadmap",
        description="Roadmap",
        scope="global",
    ),
    Keybinding(
        key="s",
        action="open_settings",
        description="Settings",
        scope="global",
    ),
    Keybinding(
        key="u",
        action="update_config",
        description="Reload",
        scope="global",
    ),
    Keybinding(
        key="d",
        action="toggle_dark",
        description="Dark",
        show_in_footer=False,
        scope="global",
    ),
    Keybinding(
        key="P",
        action="global_prompts",
        description="Global",
        show_in_footer=False,
        scope="global",
    ),
    Keybinding(
        key="f",
        action="filter_logs",
        description="Filter",
        show_in_footer=False,
        scope="global",
    ),
    Keybinding(
        key="o",
        action="toggle_sort",
        description="Order",
        show_in_footer=False,
        scope="global",
    ),
    Keybinding(
        key="t",
        action="templates",
        description="Templates",
        scope="global",
    ),
    Keybinding(
        key="T",
        action="toggle_timer",
        description="Timer",
        show_in_footer=False,
        scope="global",
    ),
    Keybinding(
        key="w",
        action="toggle_workflow_panel",
        description="Flow",
        scope="global",
    ),
    Keybinding(
        key="W",
        action="switch_workspace",
        description="Workspace",
        scope="global",
    ),
    Keybinding(
        key="M",
        action="show_metrics",
        description="Metrics",
        scope="global",
    ),
    Keybinding(
        key="B",
        action="bootstrap_project",
        description="Bootstrap",
        scope="global",
    ),
    # Project-Specific Bindings (Active when a project is selected)
    Keybinding(
        key="delete",
        action="remove_project",
        description="Remove",
        scope="project",
    ),
    Keybinding(
        key="space",
        action="toggle_project_state",
        description="Start/Stop",
        scope="project",
    ),
    Keybinding(
        key="S",
        action="start_all",
        description="All▶",
        scope="project",
    ),
    Keybinding(
        key="X",
        action="stop_all",
        description="All⏹",
        scope="project",
    ),
    Keybinding(
        key="k",
        action="skip_feature",
        description="Skip",
        scope="project",
    ),
    Keybinding(
        key="c",
        action="create_checkpoint",
        description="CheckPt",
        scope="project",
    ),
    Keybinding(
        key="C",
        action="show_checkpoints",
        description="ChkList",
        scope="project",
    ),
    Keybinding(
        key="b",
        action="config_backends",
        description="Back",
        show_in_footer=False,
        scope="project",
    ),
    Keybinding(
        key="p",
        action="config_prompts",
        description="Prmt",
        scope="project",
    ),
    Keybinding(
        key="e",
        action="edit_workflow",
        description="Editor",
        scope="project",
    ),
    Keybinding(
        key="y",
        action="show_summary",
        description="Summ",
        show_in_footer=False,
        scope="project",
    ),
    Keybinding(
        key="R",
        action="reset_project",
        description="Reset",
        scope="project",
    ),
    # Escape is special, typically global but often hidden
    Keybinding(
        key="escape",
        action="quit",
        description="Quit",
        show_in_footer=False,
        scope="global",
    ),
]
