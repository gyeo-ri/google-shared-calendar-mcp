from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from google_shared_calendar_mcp.calendar_client import CalendarClient
from google_shared_calendar_mcp.config import Config

CAL_A = "a@group.calendar.google.com"
CAL_B = "b@group.calendar.google.com"


class FakeRequest:
    def __init__(self, result: Any) -> None:
        self._result = result

    def execute(self) -> Any:
        return self._result


class FakeResource:
    """Records calls and returns canned responses keyed by method name."""

    def __init__(self, service: FakeService, name: str) -> None:
        self._service = service
        self._name = name

    def __getattr__(self, method: str):
        def call(**kwargs: Any) -> FakeRequest:
            self._service.calls.append((f"{self._name}.{method}", kwargs))
            return FakeRequest(self._service.responses.get(f"{self._name}.{method}", {}))

        return call


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.responses: dict[str, Any] = {}

    def events(self) -> FakeResource:
        return FakeResource(self, "events")

    def calendars(self) -> FakeResource:
        return FakeResource(self, "calendars")


def make_config(timezone: str | None = "Asia/Seoul", fmt: str = "Added by: {name}") -> Config:
    return Config(
        key_file=Path("key.json"),
        calendar_ids=(CAL_A, CAL_B),
        timezone=timezone,
        created_by_format=fmt,
    )


@pytest.fixture
def service() -> FakeService:
    return FakeService()


@pytest.fixture
def client(service: FakeService) -> CalendarClient:
    return CalendarClient(make_config(), service=service)
