#!/usr/bin/env python3
"""Debug script to run ruff and capture output."""

import os
import subprocess
import sys

print("Running ruff check...")
result = subprocess.run(
    [sys.executable, "-m", "ruff", "check", "src", "tests"],
    capture_output=True,
    text=True,
    cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)
print(f"Return code: {result.returncode}")
print(f"Stdout: {repr(result.stdout)}")
print(f"Stderr: {repr(result.stderr)}")

if result.stdout or result.stderr:
    print("--- STDOUT ---")
    print(result.stdout)
    print("--- STDERR ---")
    print(result.stderr)
