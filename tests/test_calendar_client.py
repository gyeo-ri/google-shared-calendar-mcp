from __future__ import annotations

import pytest

from google_shared_calendar_mcp.calendar_client import CalendarClient, CalendarNotAllowedError

from .conftest import CAL_A, CAL_B, make_config


def last_call(service):
    return service.calls[-1]


def test_default_calendar_is_first(client, service):
    client.delete_event("e1")
    assert last_call(service) == ("events.delete", {"calendarId": CAL_A, "eventId": "e1"})


def test_rejects_calendar_outside_allowlist(client, service):
    with pytest.raises(CalendarNotAllowedError):
        client.delete_event("e1", calendar_id="other@x")
    assert service.calls == []


def test_all_day_end_is_inclusive(client, service):
    service.responses["events.insert"] = {
        "id": "e1",
        "start": {"date": "2026-11-20"},
        "end": {"date": "2026-11-22"},
    }
    event = client.create_event("trip", "2026-11-20", "2026-11-21")
    body = last_call(service)[1]["body"]
    assert body["start"] == {"date": "2026-11-20"}
    assert body["end"] == {"date": "2026-11-22"}
    assert event["end"] == "2026-11-21"
    assert event["all_day"] is True


def test_naive_datetime_uses_calendar_timezone(client, service):
    service.responses["events.insert"] = {"id": "e1", "start": {}, "end": {}}
    client.create_event("dinner", "2026-11-20T19:00:00", "2026-11-20T20:00:00")
    body = last_call(service)[1]["body"]
    assert body["start"] == {"dateTime": "2026-11-20T19:00:00", "timeZone": "Asia/Seoul"}


def test_aware_datetime_is_kept(client, service):
    service.responses["events.insert"] = {"id": "e1", "start": {}, "end": {}}
    client.create_event("call", "2026-11-20T10:00:00Z", "2026-11-20T11:00:00Z")
    body = last_call(service)[1]["body"]
    assert body["start"] == {"dateTime": "2026-11-20T10:00:00+00:00"}


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-11-20", "2026-11-20T10:00:00"),
        ("2026-11-21", "2026-11-20"),
        ("2026-11-20T11:00:00", "2026-11-20T10:00:00"),
    ],
)
def test_invalid_time_ranges(client, start, end):
    with pytest.raises(ValueError):
        client.create_event("x", start, end)


def test_created_by_is_appended(service):
    client = CalendarClient(make_config(fmt="추가: {name}"), service=service)
    service.responses["events.insert"] = {"id": "e1", "start": {}, "end": {}}
    client.create_event("x", "2026-11-20", "2026-11-20", description="memo", created_by="Kim")
    assert last_call(service)[1]["body"]["description"] == "memo\n\n추가: Kim"


def test_timezone_falls_back_to_calendar_setting(service):
    client = CalendarClient(make_config(timezone=None), service=service)
    service.responses["calendars.get"] = {"timeZone": "Europe/Berlin", "summary": "Home"}
    service.responses["events.list"] = {"items": []}
    client.list_events("2026-11-20", "2026-11-21")
    client.list_events("2026-11-20", "2026-11-21")
    params = last_call(service)[1]
    assert params["timeZone"] == "Europe/Berlin"
    assert params["timeMin"] == "2026-11-20T00:00:00+01:00"
    # The calendar timezone is fetched once and cached.
    assert [c[0] for c in service.calls].count("calendars.get") == 1


def test_list_events_params(client, service):
    service.responses["events.list"] = {"items": []}
    client.list_events("2026-11-20", "2026-11-21", calendar_id=CAL_B, query="gym", max_results=999)
    params = last_call(service)[1]
    assert params["calendarId"] == CAL_B
    assert params["singleEvents"] is True
    assert params["q"] == "gym"
    assert params["maxResults"] == 250


def test_update_requires_start_and_end_together(client):
    with pytest.raises(ValueError, match="together"):
        client.update_event("e1", start="2026-11-20")


def test_update_requires_fields(client):
    with pytest.raises(ValueError, match="nothing"):
        client.update_event("e1")


def test_update_patches_only_given_fields(client, service):
    service.responses["events.patch"] = {"id": "e1", "start": {}, "end": {}}
    client.update_event("e1", summary="new")
    assert last_call(service)[1]["body"] == {"summary": "new"}
