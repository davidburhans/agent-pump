from agent_pump.utils.ui_build import run_ui_build, UIBuildError
import sys

if __name__ == "__main__":
    try:
        run_ui_build()
    except UIBuildError as e:
        print(f"Error: {e}")
        sys.exit(1)