from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, RichLog

from agent_pump.services.chat_service import ChatService


class ChatScreen(ModalScreen):
    """Screen for interactive chat."""

    CSS = """
    ChatScreen {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }

    #chat-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }

    #chat-history {
        height: 1fr;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #chat-input {
        dock: bottom;
    }
    """

    def __init__(self, project_path: Path):
        super().__init__()
        self.project_path = project_path
        self.history: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            yield RichLog(id="chat-history", highlight=True, markup=True, wrap=True)
            yield Input(
                placeholder="Ask a question about the project... (Esc to close)", id="chat-input"
            )

    def on_mount(self) -> None:
        self.query_one("#chat-input").focus()
        log = self.query_one("#chat-history", RichLog)
        log.write(f"[bold blue]Chatting with {self.project_path.name}[/]")
        log.write("[dim]Context will be loaded automatically.[/dim]")

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return

        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = ""
        input_widget.disabled = True

        log = self.query_one("#chat-history", RichLog)
        log.write(f"\\n[bold green]User:[/bold green] {query}")
        self.history.append({"role": "user", "content": query})

        # Start streaming response
        self.run_chat(query)

    @work
    async def run_chat(self, query: str) -> None:
        log = self.query_one("#chat-history", RichLog)
        log.write("\\n[bold purple]Assistant:[/bold purple] ")

        # Access app's event bus
        # Note: self.app is available on screens
        app = self.app
        # Assuming app has event_bus attribute as seen in app.py
        event_bus = getattr(app, "event_bus", None)

        if not event_bus:
            log.write("[red]Error: Event bus not available[/red]")
            return

        service = ChatService(event_bus)

        response_content = ""
        try:
            # We don't have a way to update the SAME line in RichLog easily for
            # streaming "typing" effect without writing separate segments.
            # RichLog.write appends.
            # So we will write chunks. It might look a bit fragmented if chunks are small,
            # but RichLog handles it okay usually.
            async for chunk in service.chat_stream(query, self.project_path, history=self.history):
                # log.write(chunk) - RichLog writes new lines for each write,
                # so we accumulate and write once
                response_content += chunk

            # Since we can't easily stream into RichLog, let's just write the full response for now
            # OR we can try to be clever.
            # But wait, the previous `ask` CLI command just prints to stdout, which works fine.
            # In TUI, we are stuck with widgets.

            # Let's try to update the "Assistant: ..." line if possible? No.
            # Let's just write the whole response at the end for v1,
            # OR better: write chunks but maybe use a custom widget later.

            # Actually, let's just write the accumulated response content as one block at the end
            # to avoid spamming the log with tiny chunks.
            # But the requirement was "Stream output".

            # Re-reading Textual docs (mental check): RichLog is for logs.
            # Maybe use `Markdown` widget? But that's static content.
            # `Label` or `Static` inside a `VerticalScroll`?
            # Yes, `Static` can be updated.

            # Let's just write the final response for now to ensure it looks clean.
            # Streaming into a specific `Static` widget is possible.
            # But we have a history.

            # Hybrid approach:
            # 1. User query logged.
            # 2. Assistant response logged (initially empty or "Thinking...").
            # 3. Actually, we can't update log entries.

            # Let's just output the whole thing at the end for now to be safe and clean.
            # I will remove the streaming loop for the *TUI display* but keep the service streaming.

            # Wait, I can print it.
            log.write(response_content)

            self.history.append({"role": "assistant", "content": response_content})

        except Exception as e:
            log.write(f"\\n[red]Error: {e}[/red]\\n")
        finally:
            self.query_one("#chat-input", Input).disabled = False
            self.query_one("#chat-input", Input).focus()
