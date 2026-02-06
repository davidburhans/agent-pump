import asyncio
import shutil
import time
from pathlib import Path
from unittest.mock import patch

from agent_pump.orchestrator.prompt_loader import PromptLoader

# Setup
project_path = Path("benchmark_project")
project_path.mkdir(exist_ok=True)
(project_path / ".agent-pump").mkdir(exist_ok=True)
(project_path / ".agent-pump" / "states").mkdir(exist_ok=True)
(project_path / ".agent-pump" / "backends").mkdir(exist_ok=True)

# Create a template that reads a file
(project_path / ".agent-pump" / "states" / "planning.md").write_text(
    "Context: {{ read_file('data.txt') }}"
)
(project_path / "data.txt").write_text("Some data")


async def background_task(counter):
    while True:
        counter["ticks"] += 1
        await asyncio.sleep(0.1)


async def main():
    loader = PromptLoader(project_path)

    # We want to simulate slow read
    original_read_text = Path.read_text

    def slow_read_text(self, *args, **kwargs):
        # Only slow down reading data.txt to avoid slowing down other setup reads if any
        if str(self).endswith("data.txt"):
            time.sleep(1.0)  # Blocking sleep for 1 second
        return original_read_text(self, *args, **kwargs)

    counter = {"ticks": 0}

    # Patch Path.read_text
    with patch("pathlib.Path.read_text", side_effect=slow_read_text, autospec=True):
        print("Starting build_prompt...")

        # Schedule background task
        bg_task = asyncio.create_task(background_task(counter))

        start = time.time()

        try:
            if asyncio.iscoroutinefunction(loader.build_prompt):
                await loader.build_prompt(
                    "planning", "gemini", "", context={"branch": "main"}
                )
            else:
                loader.build_prompt(
                    "planning", "gemini", "", context={"branch": "main"}
                )

        except Exception as e:
            print(f"Error: {e}")

        duration = time.time() - start

        # Stop background task
        bg_task.cancel()
        try:
            await bg_task
        except asyncio.CancelledError:
            pass

        print(f"Finished build_prompt in {duration:.2f}s")
        print(f"Background ticks during operation: {counter['ticks']}")

        # Cleanup
        if project_path.exists():
            shutil.rmtree(project_path)

        if counter["ticks"] == 0:
            print("FAIL: Event loop was blocked!")
        else:
            print("SUCCESS: Event loop was NOT blocked!")


if __name__ == "__main__":
    asyncio.run(main())
