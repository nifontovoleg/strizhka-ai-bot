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

# Кому присылать уведомления о записях и отменах (личные сообщения от бота).
# Одна строка, через запятую: @username и/или числовой chat_id.
#   ADMIN_ACCOUNTS=@olegugfv_reg59,5921878055
# Каждый админ с @username должен один раз нажать /start у бота.
# Также поддерживаются старые переменные ADMIN_USERNAMES и ADMIN_CHAT_IDS.
def _parse_admin_ids(*values) -> set:
    ids = set()
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                ids.add(int(part))
    return ids


def _parse_usernames(*values) -> list:
    result = []
    for value in values:
        for part in value.split(","):
            name = part.strip().lstrip("@").lower()
            if name and not name.lstrip("-").isdigit():
                result.append(name)
    return result


_accounts = os.getenv("ADMIN_ACCOUNTS", "")
ADMIN_CHAT_IDS = _parse_admin_ids(
    _accounts, os.getenv("ADMIN_CHAT_ID", ""), os.getenv("ADMIN_CHAT_IDS", "")
)
ADMIN_USERNAMES = _parse_usernames(
    _accounts, os.getenv("ADMIN_USERNAMES", "")
)

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
