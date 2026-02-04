import subprocess
import sys
from pathlib import Path


def build_ui():
    """Build the UI using npm."""
    project_root = Path(__file__).parent
    ui_dir = project_root / "ui"

    print(f"Building UI in {ui_dir}...")

    # Check if node_modules exists
    if not (ui_dir / "node_modules").exists():
        print("Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=ui_dir, check=True, shell=True)

    # Run build
    try:
        subprocess.run(["npm", "run", "build"], cwd=ui_dir, check=True, shell=True)
        print("UI build completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"UI build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_ui()
