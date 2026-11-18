"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ENV_KEY_FILE = "GOOGLE_SERVICE_ACCOUNT_KEY"
ENV_CALENDAR_IDS = "GOOGLE_CALENDAR_IDS"
ENV_TIMEZONE = "CALENDAR_TIMEZONE"
ENV_CREATED_BY_FORMAT = "CREATED_BY_FORMAT"

DEFAULT_CREATED_BY_FORMAT = "Added by: {name}"


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    key_file: Path
    calendar_ids: tuple[str, ...]
    timezone: str | None
    created_by_format: str

    @property
    def default_calendar_id(self) -> str:
        return self.calendar_ids[0]


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def _parse_calendar_ids(raw: str) -> tuple[str, ...]:
    ids: list[str] = []
    for part in raw.split(","):
        cid = part.strip()
        if cid and cid not in ids:
            ids.append(cid)
    if not ids:
        raise ConfigError(f"{ENV_CALENDAR_IDS} has no calendar IDs")
    return tuple(ids)


def _parse_timezone(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    tz = raw.strip()
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ConfigError(f"{ENV_TIMEZONE} is not a valid IANA timezone: {tz}") from e
    return tz


def _parse_created_by_format(raw: str | None) -> str:
    fmt = (raw or "").strip() or DEFAULT_CREATED_BY_FORMAT
    if "{name}" not in fmt:
        raise ConfigError(f"{ENV_CREATED_BY_FORMAT} must contain '{{name}}'")
    return fmt


def load_config() -> Config:
    key_file = Path(_required(ENV_KEY_FILE)).expanduser()
    if not key_file.is_file():
        raise ConfigError(f"{ENV_KEY_FILE} file not found: {key_file}")

    return Config(
        key_file=key_file,
        calendar_ids=_parse_calendar_ids(_required(ENV_CALENDAR_IDS)),
        timezone=_parse_timezone(os.environ.get(ENV_TIMEZONE)),
        created_by_format=_parse_created_by_format(os.environ.get(ENV_CREATED_BY_FORMAT)),
    )
