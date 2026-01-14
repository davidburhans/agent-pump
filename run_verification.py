import os
import subprocess


def run_command(cmd, desc):
    print(f"Running {desc}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())

        print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")

        return result.returncode
    except Exception as e:
        print(f"Error running {desc}: {e}")
        return -1


# Run all verification commands
print("Starting verification process...\n")

# Test command
test_result = run_command("uv run pytest", "tests")

# Ruff check
ruff_result = run_command("uv run ruff check .", "ruff check")

# Pyright check
pyright_result = run_command("uv run pyright", "pyright")

print("\nResults:")
print(f"Tests: {'PASS' if test_result == 0 else 'FAIL'} (exit code: {test_result})")
print(f"Ruff: {'PASS' if ruff_result == 0 else 'FAIL'} (exit code: {ruff_result})")
print(f"Pyright: {'PASS' if pyright_result == 0 else 'FAIL'} (exit code: {pyright_result})")

all_pass = (test_result == 0) and (ruff_result == 0) and (pyright_result == 0)
print(f"\nOverall: {'ALL CHECKS PASS' if all_pass else 'SOME CHECKS FAIL'}")
