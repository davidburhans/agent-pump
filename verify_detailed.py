import os
import subprocess
import sys

# Change to project directory
os.chdir(r"C:\slop\agent-pump")

print("Running tests...")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/unit/test_models.py", "-v"],
    capture_output=True,
    text=True,
)
print("TESTS OUTPUT:")
print(result.stdout)
print("TESTS ERRORS:")
print(result.stderr)
print(f"TESTS EXIT CODE: {result.returncode}")

print("\nRunning ruff check...")
result = subprocess.run(["uv", "run", "ruff", "check", "."], capture_output=True, text=True)
print("RUFF OUTPUT:")
print(result.stdout)
print("RUFF ERRORS:")
print(result.stderr)
print(f"RUFF EXIT CODE: {result.returncode}")

print("\nRunning pyright...")
result = subprocess.run(["uv", "run", "pyright"], capture_output=True, text=True)
print("PYRIGHT OUTPUT:")
print(result.stdout)
print("PYRIGHT ERRORS:")
print(result.stderr)
print(f"PYRIGHT EXIT CODE: {result.returncode}")
