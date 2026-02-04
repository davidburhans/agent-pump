
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import sys
import pytest
from agent_pump.cli import main

def test_debug_failure():
    runner = CliRunner()
    
    # Setup mock workspace
    with patch("agent_pump.models.workspace.Workspace.get_workspaces_dir") as mock_ws_dir:
        mock_dir = Path("./tmp_debug_ws")
        mock_dir.mkdir(parents=True, exist_ok=True)
        mock_ws_dir.return_value = mock_dir
        
        try:
            print("Invoking workspace delete nonexistent...")
            result = runner.invoke(main, ["workspace", "delete", "nonexistent"])
            
            with open("debug_output.txt", "w") as f:
                f.write(f"Exit code: {result.exit_code}\n")
                f.write(f"Output: {result.output}\n")
                if result.exception:
                    f.write(f"Exception: {result.exception}\n")
                    import traceback
                    f.write("Traceback:\n")
                    traceback.print_exception(*result.exc_info, file=f)
                    
        finally:
            import shutil
            if mock_dir.exists():
                shutil.rmtree(mock_dir)

if __name__ == "__main__":
    test_debug_failure()
