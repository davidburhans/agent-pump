"""Service for managing ROADMAP.md."""

import re
from typing import Any

from agent_pump.models.project import Project
from agent_pump.models.roadmap import Roadmap, RoadmapItem, RoadmapStatus


class RoadmapService:
    """Service to read and write ROADMAP.md."""

    def __init__(self, project: Project) -> None:
        """Initialize the service.

        Args:
            project: The project instance.
        """
        self.project = project
        self.roadmap_path = project.path / "ROADMAP.md"

    def load(self) -> Roadmap:
        """Load the roadmap from disk.

        Returns:
            The parsed Roadmap object.
        """
        if not self.roadmap_path.exists():
            return Roadmap()

        content = self.roadmap_path.read_text(encoding="utf-8")
        return self._parse_markdown(content)

    def save(self, roadmap: Roadmap) -> None:
        """Save the roadmap to disk.

        Args:
            roadmap: The Roadmap object to save.
        """
        content = self._generate_markdown(roadmap)
        self.roadmap_path.write_text(content, encoding="utf-8")

    def get_all_items(self) -> list[RoadmapItem]:
        """Get all roadmap items flattened.

        Returns:
            List of all RoadmapItems.
        """
        roadmap = self.load()
        return roadmap.current_sprint + roadmap.future_sprints + roadmap.deferred

    def add_item(
        self,
        title: str,
        description: str = "",
        priority: str = "Medium",
        status: RoadmapStatus = RoadmapStatus.NOT_STARTED,
        metadata: dict[str, Any] | None = None,
        section: str = "future",
    ) -> None:
        """Add a new item to the roadmap.

        Args:
            title: Item title.
            description: Item description.
            priority: Priority level.
            status: Initial status.
            metadata: Additional metadata.
            section: Target section ('current', 'future', 'deferred').
        """
        roadmap = self.load()
        item = RoadmapItem(
            title=title,
            description=description,
            priority=priority,
            status=status,
            metadata=metadata or {},
        )

        if section == "current":
            roadmap.current_sprint.append(item)
        elif section == "deferred":
            roadmap.deferred.append(item)
        else:
            roadmap.future_sprints.append(item)

        self.save(roadmap)

    def _parse_markdown(self, content: str) -> Roadmap:
        """Parse markdown content into Roadmap object."""
        roadmap = Roadmap()

        # Split by sections (## Header)
        # Using lookahead to keep the delimiter or just splitting and reconnecting
        # simpler: split by ^##
        sections = re.split(r"(?m)^## ", content)

        for section in sections:
            lines = section.strip().splitlines()
            if not lines:
                continue

            header = lines[0].strip().lower()
            body = "\n".join(lines[1:])

            if "current sprint" in header:
                roadmap.current_sprint = self._parse_items(body)
            elif "future sprints" in header:
                roadmap.future_sprints = self._parse_items(body)
            elif "deferred" in header:
                roadmap.deferred = self._parse_items(body)

        return roadmap

    def _parse_items(self, content: str) -> list[RoadmapItem]:
        """Parse a section content into list of RoadmapItems."""
        items: list[RoadmapItem] = []

        # Split by item header (### Status Title)
        # Regex to match ### [Emoji] Title
        # We need to capture the split parts
        parts = re.split(r"(?m)^### ", content)

        # First part is usually empty or intro text, ignore for now if empty
        if parts and not parts[0].strip().startswith("###"):
             # The first part is text before the first item
             parts = parts[1:]

        for part in parts:
            if not part.strip():
                continue

            lines = part.strip().splitlines()
            if not lines:
                continue

            # Parse header: "🔴 GitHub Issue Sync"
            header_line = lines[0].strip()

            # Extract status emoji and title
            status = RoadmapStatus.NOT_STARTED
            title = header_line

            match = re.match(r"^([🔴🟡⚫✅])\s+(.+)$", header_line)
            if match:
                emoji = match.group(1)
                title = match.group(2).strip()
                if emoji == "🔴":
                    status = RoadmapStatus.NOT_STARTED
                elif emoji == "🟡":
                    status = RoadmapStatus.IN_PROGRESS
                elif emoji == "⚫":
                    status = RoadmapStatus.DEFERRED
                elif emoji == "✅":
                    status = RoadmapStatus.COMPLETED

            # Parse body for metadata (Priority) and description
            description_lines = []
            priority = "Medium"
            metadata = {}

            # Simple parsing: check for **Key: Value** lines
            for line in lines[1:]:
                # Check for priority
                p_match = re.match(r"^\*\*Priority:\s*(.+?)\*\*", line.strip())
                if p_match:
                    priority = p_match.group(1)
                    continue

                # Check for GitHub Issue metadata (custom format or hidden?)
                # Maybe in the description or comments?
                # For now, let's assume we might store it in description or comments.
                # But to keep it simple, we won't parse hidden metadata yet unless we define a format.
                # If we put `<!-- metadata: {...} -->` we could parse it.

                description_lines.append(line)

            items.append(RoadmapItem(
                title=title,
                status=status,
                priority=priority,
                description="\n".join(description_lines).strip(),
                metadata=metadata
            ))

        return items

    def _generate_markdown(self, roadmap: Roadmap) -> str:
        """Generate markdown content from Roadmap object."""
        # We need to preserve the header / Status Legend.
        # Ideally we read the original file and replace sections,
        # but reconstructing is safer for consistency.

        md = [
            "# Agent Pump - Roadmap",
            "",
            "This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).",
            "",
            "## Status Legend",
            "- 🔴 **Not Started** - Queued for development",
            "- 🟡 **In Progress** - Currently being worked on",
            "- ⚫ **Deferred** - Postponed for later consideration",
            "",
            "---",
            "",
            "## Current Sprint",
            ""
        ]

        if not roadmap.current_sprint:
            md.append("(No items currently)")
            md.append("")
        else:
            for item in roadmap.current_sprint:
                md.append(self._format_item(item))

        md.append("## Future Sprints")
        md.append("")

        if not roadmap.future_sprints:
            md.append("(No items planned)")
            md.append("")
        else:
            for item in roadmap.future_sprints:
                md.append(self._format_item(item))

        if roadmap.deferred:
            md.append("## Deferred Features")
            md.append("")
            for item in roadmap.deferred:
                md.append(self._format_item(item))

        return "\n".join(md)

    def _format_item(self, item: RoadmapItem) -> str:
        """Format a single item as markdown."""
        lines = [
            f"### {item.status_emoji} {item.title}",
            f"**Priority: {item.priority}**",
            "",
            item.description,
            ""
        ]
        # We could add metadata as HTML comments if needed
        # if item.metadata:
        #    lines.append(f"<!-- metadata: {json.dumps(item.metadata)} -->")
        return "\n".join(lines)
