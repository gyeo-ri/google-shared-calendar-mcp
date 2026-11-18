from __future__ import annotations

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from google_shared_calendar_mcp.server import create_server


def test_tools_are_registered(client):
    server = create_server(client)
    names = [t.name for t in anyio.run(server.list_tools)]
    assert names == ["list_calendars", "list_events", "create_event", "update_event", "delete_event"]


def test_errors_become_tool_errors(client):
    server = create_server(client)

    async def call():
        await server.call_tool("delete_event", {"event_id": "e1", "calendar_id": "other@x"})

    with pytest.raises(ToolError, match="not allowed"):
        anyio.run(call)
