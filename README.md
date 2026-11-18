# google-shared-calendar-mcp

An [MCP](https://modelcontextprotocol.io) server for Google Calendars shared with a service account.

The server can only reach calendars that are both **shared with the service account** and **listed in its configuration**. Nothing else on the calendar owner's account is visible to it, which makes it a good fit for agents that should manage a specific shared calendar (a household or team calendar, for example) without access to anyone's personal calendars.

## Features

- Service account authentication: no browser consent flow, no refresh tokens
- Allowlist of calendar IDs, with a default calendar
- List, create, update and delete events
- Timezone handling based on each calendar's own setting
- Optional "added by" line in event descriptions

## Setup

### 1. Create a service account

1. In the Google Cloud console, select or create a project.
2. Enable the **Google Calendar API**.
3. Create a service account under **IAM & Admin > Service Accounts**. It needs no IAM roles.
4. Create a **JSON key** for the service account and keep it outside version control.

### 2. Share the calendar

1. In Google Calendar, open the calendar's **Settings and sharing**.
2. Under **Share with specific people or groups**, add the service account's email (`client_email` in the JSON key).
3. Choose **Make changes to events**.
4. Copy the **Calendar ID** under **Integrate calendar**.

Repeat for each calendar the server should manage.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Yes | Path to the service account JSON key |
| `GOOGLE_CALENDAR_IDS` | Yes | Comma-separated calendar IDs. The first one is the default |
| `CALENDAR_TIMEZONE` | No | IANA timezone (e.g. `Europe/Berlin`). Defaults to each calendar's own timezone |
| `CREATED_BY_FORMAT` | No | Format of the "added by" line. Must contain `{name}`. Default: `Added by: {name}` |

## Usage

Run with [uv](https://docs.astral.sh/uv/):

```bash
uvx --from git+https://github.com/gyeo-ri/google-shared-calendar-mcp@<tag> google-shared-calendar-mcp
```

Example MCP client configuration (stdio):

```json
{
  "mcpServers": {
    "google-shared-calendar": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/gyeo-ri/google-shared-calendar-mcp@<tag>",
        "google-shared-calendar-mcp"
      ],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_KEY": "/path/to/service-account.json",
        "GOOGLE_CALENDAR_IDS": "xxxx@group.calendar.google.com"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|---|---|
| `list_calendars` | List the calendars the server can access |
| `list_events` | List events in a time range, with optional text search |
| `create_event` | Create an event |
| `update_event` | Update the given fields of an event |
| `delete_event` | Delete an event |

All tools except `list_calendars` take an optional `calendar_id`. When omitted, the default calendar is used.

### Time format

- `YYYY-MM-DD`: all-day event. End dates are **inclusive** (`2026-01-01` to `2026-01-02` is a two-day event).
- `YYYY-MM-DDTHH:MM:SS`: interpreted in the calendar's timezone.
- `YYYY-MM-DDTHH:MM:SS+09:00`: used as given.

## Limitations

- Attendees cannot be invited. Google requires domain-wide delegation for service accounts to send invitations.
- Recurring events are listed as individual instances. Creating or editing recurrence rules is not supported.

## Development

```bash
uv sync
uv run pytest
```

## License

[MIT](LICENSE)
