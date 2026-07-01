"""Опциональная интеграция с Google Calendar.

Работает, только если config.GOOGLE_CALENDAR_ENABLED=true и настроены файлы
credentials.json / token.json. Иначе все функции — безопасные no-op, чтобы
бот работал и без Google-интеграции.

Первичная авторизация (создание token.json) выполняется один раз локально
через браузер — см. README.
"""
import logging
from datetime import datetime, timedelta

import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def is_enabled() -> bool:
    return bool(config.GOOGLE_CALENDAR_ENABLED)


def _get_service():
    """Создаёт клиент Google Calendar API. Импорты внутри — библиотеки опциональны."""
    import os

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def create_event(summary: str, description: str, start: datetime, end: datetime) -> str | None:
    """Создаёт событие в календаре. Возвращает id события или None."""
    if not is_enabled():
        return None
    try:
        service = _get_service()
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": config.SALON_TIMEZONE},
            "end": {"dateTime": end.isoformat(), "timeZone": config.SALON_TIMEZONE},
        }
        created = service.events().insert(
            calendarId=config.GOOGLE_CALENDAR_ID, body=event
        ).execute()
        return created.get("id")
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось создать событие в Google Calendar")
        return None


def delete_event(event_id: str) -> bool:
    """Удаляет событие из календаря."""
    if not is_enabled() or not event_id:
        return False
    try:
        service = _get_service()
        service.events().delete(
            calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id
        ).execute()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось удалить событие из Google Calendar")
        return False
