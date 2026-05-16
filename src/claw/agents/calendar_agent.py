"""CalendarAgent — polls Google Calendar for today's meetings via the Calendar API."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import aiosqlite

from .base import BaseMonitorAgent

logger = logging.getLogger(__name__)

_CREDENTIALS_PATH = Path("credentials.json")
_TOKEN_PATH = Path("token.json")
_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _build_service():
    """Build and return an authenticated Google Calendar service, or None if unconfigured."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning("google-api-python-client not installed; calendar monitoring disabled")
        return None

    if not _CREDENTIALS_PATH.exists():
        logger.warning("credentials.json not found; calendar monitoring disabled")
        return None

    creds = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_PATH), _SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_PATH.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


class CalendarAgent(BaseMonitorAgent):
    """Polls Google Calendar and logs meeting events for the current day."""

    agent_name = "calendar"

    def __init__(
        self,
        db: aiosqlite.Connection,
        poll_interval: int = 300,
    ) -> None:
        super().__init__(db, poll_interval)
        self._calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
        self._seen_event_ids: set[str] = set()
        self._service = None
        self._init_attempted = False

    async def collect(self) -> list[tuple[str, dict]]:
        import asyncio

        if not self._init_attempted:
            self._init_attempted = True
            self._service = await asyncio.to_thread(_build_service)

        if self._service is None:
            return []

        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        day_end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        try:
            result = await asyncio.to_thread(
                lambda: self._service.events().list(
                    calendarId=self._calendar_id,
                    timeMin=day_start,
                    timeMax=day_end,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
            )
        except Exception:
            logger.exception("[calendar] failed to fetch events")
            return []

        events: list[tuple[str, dict]] = []
        for item in result.get("items", []):
            event_id = item.get("id", "")
            if event_id in self._seen_event_ids:
                continue
            self._seen_event_ids.add(event_id)

            start = item.get("start", {})
            end = item.get("end", {})
            start_str = start.get("dateTime") or start.get("date", "")
            end_str = end.get("dateTime") or end.get("date", "")

            duration_minutes = 0
            if start_str and end_str:
                try:
                    s = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    e = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    duration_minutes = int((e - s).total_seconds() / 60)
                except ValueError:
                    pass

            payload = {
                "event_id": event_id,
                "title": item.get("summary", "(no title)"),
                "start": start_str,
                "end": end_str,
                "duration_minutes": duration_minutes,
                "attendee_count": len(item.get("attendees", [])),
                "is_recurring": bool(item.get("recurringEventId")),
            }
            events.append(("meeting_event", payload))
            logger.info("[calendar] meeting: %s (%dmin)", payload["title"], duration_minutes)

        return events
