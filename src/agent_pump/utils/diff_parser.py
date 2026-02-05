import re

from agent_pump.models.diff import DiffChangeType, DiffFile, DiffHunk


def parse_git_diff(diff_output: str) -> list[DiffFile]:
    """Parse git unified diff output into DiffFile objects.

    Args:
        diff_output: The raw output from `git diff` or similar command.

    Returns:
        List of DiffFile objects representing the changes.
    """
    files: list[DiffFile] = []

    if not diff_output.strip():
        return files

    # Git diffs usually start with "diff --git a/path b/path"
    # We split by this marker to separate files.
    # Note: split will give an empty first element if string starts with delimiter
    parts = diff_output.split("diff --git ")

    for part in parts:
        if not part.strip():
            continue

        parsed_file = _parse_single_file_diff(part)
        if parsed_file:
            files.append(parsed_file)

    return files


def _parse_single_file_diff(raw_content: str) -> DiffFile | None:
    lines = raw_content.splitlines()
    if not lines:
        return None

    # Line 0 is usually "a/path b/path" (paths might be quoted if they contain spaces)
    # We need to parse headers to determine status and filenames

    header_lines = []
    hunk_lines = []
    in_hunks = False

    for line in lines:
        if line.startswith("@@"):
            in_hunks = True

        if in_hunks:
            hunk_lines.append(line)
        else:
            header_lines.append(line)

    # Parse headers to get metadata
    path_a, path_b = _extract_paths_from_header(header_lines[0])
    status, old_path = _determine_status_and_paths(header_lines, path_a, path_b)

    # If no path detected (binary file or weird format), skip
    final_path = path_b if path_b else path_a
    if not final_path:
        return None

    # Parse hunks
    hunks = _parse_hunks(hunk_lines)

    return DiffFile(path=final_path, status=status, hunks=hunks, old_path=old_path)


def _extract_paths_from_header(first_line: str) -> tuple[str | None, str | None]:
    """Extract a/path and b/path from 'a/src/foo.py b/src/foo.py'."""
    # This is naive and fails on filenames with spaces if not careful.
    # But git usually outputs `a/path with spaces` `b/path with spaces`
    # or quotes them.
    # Regex approach for standard `a/... b/...` pattern

    # Try to find the separation between a/ and b/
    # A robust regex for 'a/(.*) b/(.*)'
    # Note: git can be configured with different prefixes, but we assume defaults.

    # Simple split might work for simple filenames
    # But let's try to match typical git output

    # The line is: "a/path/to/file.py b/path/to/file.py"
    # Or "a/path with spaces b/path with spaces"

    # If we assume no quoted paths for now (simplification):
    # Just split by space doesn't work.

    # Strategy: Look for " b/" which separates the two.
    # But " b/" could be part of the filename.

    # Given this is a utility, let's try a heuristic:
    # Git diff header is usually `a/{path} b/{path}`.
    # If it's a rename, headers might say `rename from ...`

    # Let's use a regex that handles unquoted paths fairly well.
    # It attempts to match a/ followed by content, then space, then b/ followed by content
    # content matches until the end of line.

    match = re.match(r"^a/(.+) b/(.+)$", first_line)
    if match:
        return match.group(1), match.group(2)

    # Fallback/Empty handling
    return None, None


def _determine_status_and_paths(
    headers: list[str], path_a: str | None, path_b: str | None
) -> tuple[DiffChangeType, str | None]:
    """Determine status (ADDED, DELETED, MODIFIED, RENAMED) and old path."""
    status = DiffChangeType.MODIFIED
    old_path = None

    is_new = any(line.startswith("new file mode") for line in headers)
    is_deleted = any(line.startswith("deleted file mode") for line in headers)
    is_renamed = any(line.startswith("rename from") for line in headers)

    if is_new:
        status = DiffChangeType.ADDED
    elif is_deleted:
        status = DiffChangeType.DELETED
    elif is_renamed:
        status = DiffChangeType.RENAMED
        old_path = path_a

    return status, old_path


def _parse_hunks(lines: list[str]) -> list[DiffHunk]:
    hunks = []
    current_header = ""
    current_lines = []

    for line in lines:
        if line.startswith("@@"):
            # Save previous hunk if exists
            if current_header:
                hunks.append(DiffHunk(header=current_header, lines=current_lines))

            current_header = line
            current_lines = []
        else:
            current_lines.append(line)

    # Append last hunk
    if current_header:
        hunks.append(DiffHunk(header=current_header, lines=current_lines))

    return hunks
