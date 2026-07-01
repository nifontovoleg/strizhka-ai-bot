"""Хранилище записей на приём (SQLite)."""
import sqlite3
from contextlib import contextmanager

import config


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id      INTEGER NOT NULL,
                service      TEXT    NOT NULL,
                start        TEXT    NOT NULL,   -- ISO datetime, начало
                end          TEXT    NOT NULL,   -- ISO datetime, конец
                client_name  TEXT,
                client_phone TEXT,
                gcal_event_id TEXT,              -- id события в Google Calendar
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Мягкая миграция для старых баз без столбца gcal_event_id.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()]
        if "gcal_event_id" not in cols:
            conn.execute("ALTER TABLE bookings ADD COLUMN gcal_event_id TEXT")


def get_bookings_for_day(day_iso: str):
    """Возвращает записи за конкретный день (YYYY-MM-DD)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE substr(start, 1, 10) = ? ORDER BY start",
            (day_iso,),
        ).fetchall()
        return [dict(r) for r in rows]


def has_overlap(start_iso: str, end_iso: str) -> bool:
    """Проверяет пересечение с существующими записями."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM bookings WHERE start < ? AND end > ? LIMIT 1",
            (end_iso, start_iso),
        ).fetchone()
        return row is not None


def add_booking(chat_id, service, start_iso, end_iso, client_name, client_phone) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO bookings (chat_id, service, start, end, client_name, client_phone)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chat_id, service, start_iso, end_iso, client_name, client_phone),
        )
        return cur.lastrowid


def set_gcal_event(booking_id: int, event_id: str) -> None:
    """Сохраняет id события Google Calendar для записи."""
    with _conn() as conn:
        conn.execute(
            "UPDATE bookings SET gcal_event_id = ? WHERE id = ?",
            (event_id, booking_id),
        )


def get_upcoming_bookings(chat_id: int, now_iso: str):
    """Возвращает будущие записи клиента (по chat_id)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE chat_id = ? AND end >= ? ORDER BY start",
            (chat_id, now_iso),
        ).fetchall()
        return [dict(r) for r in rows]


def get_booking(booking_id: int, chat_id: int):
    """Возвращает запись по id, если она принадлежит этому клиенту."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM bookings WHERE id = ? AND chat_id = ?",
            (booking_id, chat_id),
        ).fetchone()
        return dict(row) if row else None


def delete_booking(booking_id: int, chat_id: int) -> bool:
    """Удаляет запись клиента. Возвращает True, если что-то удалено."""
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM bookings WHERE id = ? AND chat_id = ?",
            (booking_id, chat_id),
        )
        return cur.rowcount > 0
