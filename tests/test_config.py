from __future__ import annotations

import pytest

from google_shared_calendar_mcp.config import ConfigError, load_config


@pytest.fixture
def env(monkeypatch, tmp_path):
    key = tmp_path / "key.json"
    key.write_text("{}")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_KEY", str(key))
    monkeypatch.setenv("GOOGLE_CALENDAR_IDS", "a@x, b@x ,a@x,")
    monkeypatch.delenv("CALENDAR_TIMEZONE", raising=False)
    monkeypatch.delenv("CREATED_BY_FORMAT", raising=False)
    return monkeypatch


def test_loads_and_dedupes_calendar_ids(env):
    config = load_config()
    assert config.calendar_ids == ("a@x", "b@x")
    assert config.default_calendar_id == "a@x"
    assert config.timezone is None
    assert config.created_by_format == "Added by: {name}"


def test_missing_key_env(env):
    env.delenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    with pytest.raises(ConfigError, match="GOOGLE_SERVICE_ACCOUNT_KEY"):
        load_config()


def test_key_file_not_found(env, tmp_path):
    env.setenv("GOOGLE_SERVICE_ACCOUNT_KEY", str(tmp_path / "missing.json"))
    with pytest.raises(ConfigError, match="not found"):
        load_config()


def test_empty_calendar_ids(env):
    env.setenv("GOOGLE_CALENDAR_IDS", " , ")
    with pytest.raises(ConfigError, match="no calendar IDs"):
        load_config()


def test_invalid_timezone(env):
    env.setenv("CALENDAR_TIMEZONE", "Mars/Olympus")
    with pytest.raises(ConfigError, match="timezone"):
        load_config()


def test_created_by_format_requires_name(env):
    env.setenv("CREATED_BY_FORMAT", "Added by someone")
    with pytest.raises(ConfigError, match="name"):
        load_config()
