"""Конфигурация приложения: читает переменные окружения из .env."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# GigaChat (Sber). Ключ авторизации (Authorization key) из личного кабинета.
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat")
# По умолчанию проверка SSL отключена, чтобы не требовать установку
# «Russian Trusted Root CA». Для продакшена задайте true и укажите GIGACHAT_CA_BUNDLE_FILE.
GIGACHAT_VERIFY_SSL = os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() in ("1", "true", "yes")
GIGACHAT_CA_BUNDLE_FILE = os.getenv("GIGACHAT_CA_BUNDLE_FILE") or None

SALON_TIMEZONE = os.getenv("SALON_TIMEZONE", "Europe/Moscow")
TZ = ZoneInfo(SALON_TIMEZONE)

DB_PATH = os.getenv("DB_PATH", "bookings.db")

# ID чата администратора для уведомлений о новых записях (необязательно).
# Узнать свой ID можно у бота @userinfobot. Если пусто — уведомления отключены.
_admin = os.getenv("ADMIN_CHAT_ID", "").strip()
ADMIN_CHAT_ID = int(_admin) if _admin.lstrip("-").isdigit() else None

# Google Calendar (необязательно). Включается, если GOOGLE_CALENDAR_ENABLED=true
# и рядом лежит credentials.json (OAuth client) из Google Cloud Console.
GOOGLE_CALENDAR_ENABLED = os.getenv("GOOGLE_CALENDAR_ENABLED", "false").lower() in ("1", "true", "yes")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


def validate() -> None:
    """Проверяет наличие обязательных настроек перед запуском."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GIGACHAT_CREDENTIALS:
        missing.append("GIGACHAT_CREDENTIALS")
    if missing:
        raise SystemExit(
            "Не заданы обязательные переменные окружения: "
            + ", ".join(missing)
            + ".\nСкопируйте .env.example в .env и заполните значения."
        )
