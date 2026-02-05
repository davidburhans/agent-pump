from agent_pump.models.diff import DiffChangeType
from agent_pump.utils.diff_parser import parse_git_diff


def test_parse_simple_diff():
    diff_output = """diff --git a/src/foo.py b/src/foo.py
index 1234567..890abcd 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,4 @@
 import os
-print("Hello")
+print("Hello World")
+print("New line")
"""
    files = parse_git_diff(diff_output)
    assert len(files) == 1

    file = files[0]
    assert file.path == "src/foo.py"
    assert file.status == DiffChangeType.MODIFIED
    assert len(file.hunks) == 1

    hunk = file.hunks[0]
    assert hunk.header == "@@ -1,3 +1,4 @@"
    assert len(hunk.lines) == 4
    assert hunk.lines[0] == ' import os'
    assert hunk.lines[1] == '-print("Hello")'
    assert hunk.lines[2] == '+print("Hello World")'
    assert hunk.lines[3] == '+print("New line")'
    # Note: The parser implementation accumulates lines.
    # Let's check the lines more carefully based on the implementation logic.

def test_parse_new_file():
    diff_output = """diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,2 @@
+line 1
+line 2
"""
    files = parse_git_diff(diff_output)
    assert len(files) == 1
    assert files[0].path == "new_file.py"
    assert files[0].status == DiffChangeType.ADDED

def test_parse_deleted_file():
    diff_output = """diff --git a/old_file.py b/old_file.py
deleted file mode 100644
index 1234567..0000000
--- a/old_file.py
+++ /dev/null
@@ -1,1 +0,0 @@
-content
"""
    files = parse_git_diff(diff_output)
    assert len(files) == 1
    assert files[0].path == "old_file.py"  # fallback to a path if b is /dev/null
    # Actually, the parser implementation uses: final_path = path_b if path_b else path_a
    # In deletion, b/old_file.py might still be in header line "diff --git a/... b/..."
    # The header line is "diff --git a/old_file.py b/old_file.py"
    # So path_b is "old_file.py".
    assert files[0].status == DiffChangeType.DELETED

def test_parse_multiple_files():
    diff_output = """diff --git a/file1.py b/file1.py
index ...
--- a/file1.py
+++ b/file1.py
@@ -1 +1 @@
-a
+b
diff --git a/file2.py b/file2.py
index ...
--- a/file2.py
+++ b/file2.py
@@ -1 +1 @@
-x
+y
"""
    files = parse_git_diff(diff_output)
    assert len(files) == 2
    assert files[0].path == "file1.py"
    assert files[1].path == "file2.py"
