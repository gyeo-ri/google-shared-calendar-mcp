"""Thin wrapper around the Google Calendar API for allowlisted calendars."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import Config

SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
)


class CalendarError(Exception):
    """Base error for calendar operations."""


class CalendarNotAllowedError(CalendarError):
    """Raised when a calendar ID is not in the allowlist."""


class CalendarAPIError(CalendarError):
    """Raised when the Google Calendar API returns an error."""


def build_service(config: Config) -> Any:
    credentials = service_account.Credentials.from_service_account_file(
        str(config.key_file), scopes=list(SCOPES)
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _is_date_only(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-"


class CalendarClient:
    def __init__(self, config: Config, service: Any | None = None) -> None:
        self._config = config
        self._service = service if service is not None else build_service(config)
        self._timezones: dict[str, str] = {}

    # --- helpers -----------------------------------------------------------

    def _resolve_calendar(self, calendar_id: str | None) -> str:
        if calendar_id is None:
            return self._config.default_calendar_id
        if calendar_id not in self._config.calendar_ids:
            raise CalendarNotAllowedError(f"calendar is not allowed: {calendar_id}")
        return calendar_id

    def _execute(self, request: Any) -> Any:
        try:
            return request.execute()
        except HttpError as e:
            raise CalendarAPIError(f"Google Calendar API error {e.status_code}: {e.reason}") from e

    def _get_calendar(self, calendar_id: str) -> dict[str, Any]:
        return self._execute(self._service.calendars().get(calendarId=calendar_id))

    def timezone_for(self, calendar_id: str) -> str:
        if self._config.timezone:
            return self._config.timezone
        if calendar_id not in self._timezones:
            self._timezones[calendar_id] = self._get_calendar(calendar_id).get("timeZone", "UTC")
        return self._timezones[calendar_id]

    def _to_rfc3339(self, value: str, tz: str) -> str:
        """Convert a query bound (date or datetime) to RFC 3339 with an offset."""
        if _is_date_only(value):
            dt = datetime.combine(date.fromisoformat(value), datetime.min.time())
        else:
            dt = _parse_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        return dt.isoformat()

    def _event_times(self, start: str, end: str, tz: str) -> tuple[dict, dict]:
        """Build start/end bodies. All-day end dates are inclusive on input."""
        start_all_day, end_all_day = _is_date_only(start), _is_date_only(end)
        if start_all_day != end_all_day:
            raise ValueError("start and end must both be dates or both be datetimes")

        if start_all_day:
            start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
            if end_d < start_d:
                raise ValueError("end must not be before start")
            # Google treats all-day end dates as exclusive.
            return (
                {"date": start_d.isoformat()},
                {"date": (end_d + timedelta(days=1)).isoformat()},
            )

        start_dt, end_dt = _parse_datetime(start), _parse_datetime(end)
        bodies = []
        for dt in (start_dt, end_dt):
            if dt.tzinfo is None:
                bodies.append({"dateTime": dt.isoformat(), "timeZone": tz})
            else:
                bodies.append({"dateTime": dt.isoformat()})
        aware_start = start_dt if start_dt.tzinfo else start_dt.replace(tzinfo=ZoneInfo(tz))
        aware_end = end_dt if end_dt.tzinfo else end_dt.replace(tzinfo=ZoneInfo(tz))
        if aware_end <= aware_start:
            raise ValueError("end must be after start")
        return bodies[0], bodies[1]

    def _append_created_by(self, description: str | None, created_by: str | None) -> str | None:
        if not created_by:
            return description
        line = self._config.created_by_format.format(name=created_by)
        return f"{description}\n\n{line}" if description else line

    @staticmethod
    def _normalize(event: dict[str, Any], calendar_id: str) -> dict[str, Any]:
        start, end = event.get("start", {}), event.get("end", {})
        all_day = "date" in start
        if all_day:
            start_value = start["date"]
            # Convert the exclusive end date back to inclusive.
            end_value = (date.fromisoformat(end["date"]) - timedelta(days=1)).isoformat()
        else:
            start_value, end_value = start.get("dateTime"), end.get("dateTime")
        return {
            "event_id": event["id"],
            "calendar_id": calendar_id,
            "summary": event.get("summary", ""),
            "start": start_value,
            "end": end_value,
            "all_day": all_day,
            "description": event.get("description"),
            "location": event.get("location"),
            "recurring": "recurringEventId" in event,
        }

    # --- operations --------------------------------------------------------

    def list_calendars(self) -> list[dict[str, Any]]:
        result = []
        for cid in self._config.calendar_ids:
            cal = self._get_calendar(cid)
            result.append(
                {
                    "calendar_id": cid,
                    "summary": cal.get("summary", ""),
                    "timezone": self.timezone_for(cid),
                    "default": cid == self._config.default_calendar_id,
                }
            )
        return result

    def list_events(
        self,
        time_min: str,
        time_max: str,
        calendar_id: str | None = None,
        query: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        cid = self._resolve_calendar(calendar_id)
        tz = self.timezone_for(cid)
        params: dict[str, Any] = {
            "calendarId": cid,
            "timeMin": self._to_rfc3339(time_min, tz),
            "timeMax": self._to_rfc3339(time_max, tz),
            "singleEvents": True,
            "orderBy": "startTime",
            "timeZone": tz,
            "maxResults": max(1, min(max_results, 250)),
        }
        if query:
            params["q"] = query
        response = self._execute(self._service.events().list(**params))
        return [self._normalize(e, cid) for e in response.get("items", [])]

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        calendar_id: str | None = None,
        description: str | None = None,
        location: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        cid = self._resolve_calendar(calendar_id)
        start_body, end_body = self._event_times(start, end, self.timezone_for(cid))
        body: dict[str, Any] = {"summary": summary, "start": start_body, "end": end_body}
        desc = self._append_created_by(description, created_by)
        if desc:
            body["description"] = desc
        if location:
            body["location"] = location
        event = self._execute(self._service.events().insert(calendarId=cid, body=body))
        return self._normalize(event, cid)

    def update_event(
        self,
        event_id: str,
        calendar_id: str | None = None,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        cid = self._resolve_calendar(calendar_id)
        body: dict[str, Any] = {}
        if (start is None) != (end is None):
            raise ValueError("start and end must be provided together")
        if start is not None and end is not None:
            body["start"], body["end"] = self._event_times(start, end, self.timezone_for(cid))
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        if not body:
            raise ValueError("nothing to update")
        event = self._execute(
            self._service.events().patch(calendarId=cid, eventId=event_id, body=body)
        )
        return self._normalize(event, cid)

    def delete_event(self, event_id: str, calendar_id: str | None = None) -> dict[str, Any]:
        cid = self._resolve_calendar(calendar_id)
        self._execute(self._service.events().delete(calendarId=cid, eventId=event_id))
        return {"event_id": event_id, "calendar_id": cid, "deleted": True}
