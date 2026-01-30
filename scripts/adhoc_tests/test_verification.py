#!/usr/bin/env python3
"""Test script to run verification commands and see output."""

import os
import subprocess


def run_command(cmd, desc):
    print(f"Running {desc}...")
    print(f"Command: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")),
        )

        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")

        return result.returncode == 0
    except Exception as e:
        print(f"Error running {desc}: {e}")
        return False


if __name__ == "__main__":
    print("Starting verification process...\n")

    # Test command
    test_success = run_command(
        "python -m pytest tests/unit/test_verification_executor.py -v", "specific test"
    )

    # Ruff check
    ruff_success = run_command("python -m ruff check .", "ruff check")

    print("\nResults:")
    print(f"Specific test: {'PASS' if test_success else 'FAIL'}")
    print(f"Ruff check: {'PASS' if ruff_success else 'FAIL'}")

    all_pass = test_success and ruff_success
    print(f"\nOverall: {'ALL CHECKS PASS' if all_pass else 'SOME CHECKS FAIL'}")
