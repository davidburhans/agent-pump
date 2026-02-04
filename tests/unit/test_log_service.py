import asyncio
from pathlib import Path

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import LogEntryEvent
from agent_pump.models.log import LogEntry
from agent_pump.services.log_service import LogBuffer, LogService


class TestLogBuffer:
    def test_add_and_get_recent(self):
        buffer = LogBuffer(max_size=5)
        for i in range(10):
            entry = LogEntry(
                timestamp="12:00",
                message=f"msg {i}",
                project_path=None,
                state="idle",
                task=None
            )
            buffer.add(entry)

        recent = buffer.get_recent(limit=3)
        assert len(recent) == 3
        assert recent[0].message == "msg 7"
        assert recent[2].message == "msg 9"

        # Check max size constraint
        assert len(buffer.buffer) == 5
        assert buffer.buffer[0].message == "msg 5"

    def test_filtering(self):
        buffer = LogBuffer()
        buffer.add(LogEntry("t", "A", None, "planning", None))
        buffer.add(LogEntry("t", "B", None, "implementing", None))
        buffer.add(LogEntry("t", "C", None, "planning", None))

        recent = buffer.get_recent(limit=10, filter_func=lambda e: e.state == "planning")
        assert len(recent) == 2
        assert recent[0].message == "A"
        assert recent[1].message == "C"

class TestLogService:
    @pytest.mark.asyncio
    async def test_log_service_integration(self):
        event_bus = EventBus()
        service = LogService(event_bus)
        await service.start()

        # Wait for subscription to initialize
        await asyncio.sleep(0.1)

        project_path = Path("/tmp/test_project")

        # Publish event
        event = LogEntryEvent(
            message="Test Message",
            project_path=project_path,
            state="running",
            task="testing"
        )
        await event_bus.publish(event)

        # Allow async task to process
        await asyncio.sleep(0.1)

        # Check buffer
        buffer = service._get_buffer(project_path)
        assert len(buffer.buffer) == 1
        assert buffer.buffer[0].message == "Test Message"

        # Check streaming (history)
        stream = service.stream(project_path)
        # We need to manually iterate since it's an async generator

        # Let's add another event while streaming
        async def produce():
            await asyncio.sleep(0.1)
            await event_bus.publish(LogEntryEvent(message="Future", project_path=project_path))

        asyncio.create_task(produce())

        items = []
        async for entry in stream:
            items.append(entry.message)
            if len(items) >= 2:
                break

        assert "Test Message" in items
        assert "Future" in items
