"""Utility for parsing and reordering ROADMAP.md files."""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RoadmapFeature:
    """Represents a feature in the roadmap."""

    title: str
    status: str  # e.g., "🔴 Not Started", "🟡 In Progress", "🟢 Complete"
    priority: str | None = None
    description: str = ""
    acceptance_criteria: list[str] | None = None
    raw_content: str = ""  # The full markdown block for this feature

    def __post_init__(self):
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []


class RoadmapParser:
    """Parses and updates ROADMAP.md files."""

    FEATURE_PATTERN = re.compile(
        r"### ([\U0001f534\U0001f7e1\U0001f311\U0001f7e2]) ([^\n]+)\n+"  # Status icon + Title
        r"(?:\*\*Priority: ([^\n]+)\*\*\n+)?"  # Optional Priority
        r"(.*?)\n+"  # Description
        r"(?:\*\*Acceptance Criteria:\*\*\n+((?:- [^\n]+\n?)*))?",  # Optional Acceptance Criteria
        re.DOTALL,
    )

    def __init__(self, path: Path):
        self.path = path
        self.content = ""
        self.features = []
        self.preamble = ""  # Content before features
        self.postamble = ""  # Content after features (if any)
        # To store different sections (Current Sprint, Future Enhancements, etc.)
        self.sections = {}

    def parse(self, content: str | None = None) -> list[RoadmapFeature]:
        """
        Parse the ROADMAP.md file.

        Args:
            content: Optional content string to parse directly without reading file.
        """
        if content:
            self.content = content
        elif self.path.exists():
            self.content = self.path.read_text(encoding="utf-8")
        else:
            return []

        # Split into sections based on headers
        sections = re.split(r"\n(## [^\n]+)\n", self.content)

        # sections[0] is preamble
        self.preamble = sections[0]

        current_features = []

        # Process sections
        for i in range(1, len(sections), 2):
            header = sections[i]
            body = sections[i + 1] if i + 1 < len(sections) else ""

            # Find features in this section
            # We want to keep track of where features are
            feature_matches = list(self.FEATURE_PATTERN.finditer(body))

            section_features = []
            for match in feature_matches:
                full_text = match.group(0)
                status_icon = match.group(1)
                title = match.group(2).strip()
                priority = match.group(3)
                description = match.group(4).strip()
                criteria_raw = match.group(5)
                if criteria_raw:
                    criteria = [c[2:].strip() for c in criteria_raw.strip().split("\n") if c.startswith("- ")]
                else:
                    criteria = []

                feature = RoadmapFeature(
                    title=title,
                    status=status_icon,
                    priority=priority,
                    description=description,
                    acceptance_criteria=criteria,
                    raw_content=full_text,
                )
                section_features.append(feature)

            self.sections[header] = {"body": body, "features": section_features}
            current_features.extend(section_features)

        self.features = current_features
        return self.features

    async def parse_async(self) -> list[RoadmapFeature]:
        """Parse the ROADMAP.md file asynchronously."""
        return await asyncio.to_thread(self.parse)

    def get_uncompleted_features(self) -> list[RoadmapFeature]:
        """Return only uncompleted features."""
        return [f for f in self.features if "🔴" in f.status or "🟡" in f.status]

    def save_with_order(self, reordered_features: list[RoadmapFeature]) -> None:
        """
        Save ROADMAP.md with uncompleted features in the new order.

        This is tricky because we want to preserve the rest of the file.
        We'll replace features in 'Current Sprint' and 'Future Enhancements'
        with the new ordered list.
        """
        # For simplicity, we'll put all reordered features into 'Future Enhancements'
        # or keep them in their original sections if we want to be fancy.
        # But usually prioritization means moving things between these two.

        new_content = self.preamble

        # Find headers for Sprint and Future
        # If they don't exist, we'll have to be careful.

        reordered_titles = {f.title for f in reordered_features}

        for header, data in self.sections.items():
            new_content += f"\n{header}\n"

            if "Completed" in header or "Recently Completed" in header:
                # Keep as is
                new_content += data["body"]
                continue

            # For Current Sprint and Future Enhancements, we replace features
            # that are in our reordered list.

            body = data["body"]

            # We'll rebuild the body
            # First, find what features were originally here but ARE NOT in reordered list
            # (e.g. completed ones if they weren't filtered out, or deferred)

            original_features = data["features"]
            features_to_stay = [f for f in original_features if f.title not in reordered_titles]

            # If this is Future Enhancements, we put all reordered features here
            # (unless some are in Current Sprint).
            # Actually, a simpler approach:
            # 1. Take all features currently in Current Sprint and Future Enhancements.
            # 2. Reorder them according to the input.
            # 3. Put them back.

            if "Future Enhancements" in header:
                # Put all reordered features here for now
                for f in reordered_features:
                    new_content += f"\n### {f.status} {f.title}\n"
                    if f.priority:
                        new_content += f"**Priority: {f.priority}**\n\n"
                    new_content += f"{f.description}\n\n"
                    new_content += "**Acceptance Criteria:**\n"
                    if f.acceptance_criteria:
                        for c in f.acceptance_criteria:
                            new_content += f"- {c}\n"
                    new_content += "\n---\n"
            elif "Current Sprint" in header:
                # Put back features that are not in the reordered list
                # (e.g. completed ones if they were here)
                for f in features_to_stay:
                    new_content += f.raw_content + "\n---\n"
            else:
                new_content += body

        self.path.write_text(new_content, encoding="utf-8")
