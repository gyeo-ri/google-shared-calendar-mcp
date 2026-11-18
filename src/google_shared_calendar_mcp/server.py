"""MCP server exposing tools for Google Calendars shared with a service account."""

from __future__ import annotations

import sys
from functools import partial
from typing import Annotated, Any, Callable

import anyio
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .calendar_client import CalendarClient, CalendarError
from .config import ConfigError, load_config

INSTRUCTIONS = """\
Manage events on Google Calendars shared with this server's service account.

Time format:
- Date only (YYYY-MM-DD) means an all-day event. All-day end dates are inclusive.
- Datetime without an offset (YYYY-MM-DDTHH:MM:SS) uses the calendar's timezone.
- Datetime with an offset (e.g. 2026-01-01T09:00:00+09:00) is used as is.

Omit calendar_id to use the default calendar. Call list_calendars to see the
calendars this server can access. Use event_id from list_events to update or
delete an event.
"""

CalendarId = Annotated[
    str | None,
    Field(description="Calendar ID from list_calendars. Omit to use the default calendar."),
]
EventId = Annotated[str, Field(description="event_id returned by list_events or create_event.")]
Start = Annotated[str, Field(description="Start date (YYYY-MM-DD) or datetime (ISO 8601).")]
End = Annotated[
    str,
    Field(description="End date (YYYY-MM-DD, inclusive) or datetime (ISO 8601)."),
]


async def _call(func: Callable[..., Any], /, **kwargs: Any) -> Any:
    try:
        return await anyio.to_thread.run_sync(partial(func, **kwargs))
    except (CalendarError, ValueError) as e:
        raise ToolError(str(e)) from e


def create_server(client: CalendarClient) -> MCPServer:
    mcp = MCPServer(
        "google-shared-calendar",
        instructions=INSTRUCTIONS,
        version=__version__,
    )

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def list_calendars() -> list[dict[str, Any]]:
        """List the calendars this server can access."""
        return await _call(client.list_calendars)

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def list_events(
        time_min: Annotated[str, Field(description="Range start, date or datetime (inclusive).")],
        time_max: Annotated[str, Field(description="Range end, date or datetime (exclusive).")],
        calendar_id: CalendarId = None,
        query: Annotated[str | None, Field(description="Free-text search filter.")] = None,
        max_results: Annotated[int, Field(ge=1, le=250, description="Maximum events.")] = 50,
    ) -> list[dict[str, Any]]:
        """List events in a time range. Recurring events are expanded into instances."""
        return await _call(
            client.list_events,
            time_min=time_min,
            time_max=time_max,
            calendar_id=calendar_id,
            query=query,
            max_results=max_results,
        )

    @mcp.tool()
    async def create_event(
        summary: Annotated[str, Field(description="Event title.")],
        start: Start,
        end: End,
        calendar_id: CalendarId = None,
        description: Annotated[str | None, Field(description="Event description.")] = None,
        location: Annotated[str | None, Field(description="Event location.")] = None,
        created_by: Annotated[
            str | None,
            Field(description="Name of the person who requested the event, recorded in the description."),
        ] = None,
    ) -> dict[str, Any]:
        """Create an event."""
        return await _call(
            client.create_event,
            summary=summary,
            start=start,
            end=end,
            calendar_id=calendar_id,
            description=description,
            location=location,
            created_by=created_by,
        )

    @mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
    async def update_event(
        event_id: EventId,
        calendar_id: CalendarId = None,
        summary: Annotated[str | None, Field(description="New title.")] = None,
        start: Annotated[str | None, Field(description="New start. Requires end.")] = None,
        end: Annotated[str | None, Field(description="New end. Requires start.")] = None,
        description: Annotated[str | None, Field(description="New description (replaces).")] = None,
        location: Annotated[str | None, Field(description="New location.")] = None,
    ) -> dict[str, Any]:
        """Update fields of an event. Only the given fields are changed."""
        return await _call(
            client.update_event,
            event_id=event_id,
            calendar_id=calendar_id,
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=location,
        )

    @mcp.tool(annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True))
    async def delete_event(event_id: EventId, calendar_id: CalendarId = None) -> dict[str, Any]:
        """Delete an event."""
        return await _call(client.delete_event, event_id=event_id, calendar_id=calendar_id)

    return mcp


def main() -> None:
    try:
        config = load_config()
    except ConfigError as e:
        print(f"google-shared-calendar-mcp: {e}", file=sys.stderr)
        sys.exit(1)
    create_server(CalendarClient(config)).run(transport="stdio")


if __name__ == "__main__":
    main()
