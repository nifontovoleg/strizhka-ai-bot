"""Логика расписания: расчёт свободных слотов и создание записи."""
from datetime import datetime, timedelta

import config
import database as db
import knowledge_base as kb


def _today():
    return datetime.now(config.TZ).replace(microsecond=0)


def parse_date(date_str: str) -> datetime | None:
    """Разбирает дату из 'YYYY-MM-DD', 'today'/'сегодня', 'tomorrow'/'завтра'."""
    s = (date_str or "").strip().lower()
    now = _today()
    if s in ("today", "сегодня"):
        return now
    if s in ("tomorrow", "завтра"):
        return now + timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%d.%m":
                dt = dt.replace(year=now.year)
            return dt.replace(tzinfo=config.TZ)
        except ValueError:
            continue
    return None


def _in_lunch(hour_start: datetime, hour_end: datetime) -> bool:
    lunch_start = hour_start.replace(hour=kb.LUNCH_START_HOUR, minute=0)
    lunch_end = hour_start.replace(hour=kb.LUNCH_END_HOUR, minute=0)
    return hour_start < lunch_end and hour_end > lunch_start


def available_slots(date_str: str, service_name: str) -> dict:
    """Возвращает список свободных слотов для услуги на указанный день."""
    day = parse_date(date_str)
    if day is None:
        return {"ok": False, "error": "Не удалось распознать дату. Уточните в формате ГГГГ-ММ-ДД, 'сегодня' или 'завтра'."}

    service = kb.find_service(service_name)
    if service is None:
        return {"ok": False, "error": f"Услуга «{service_name}» не найдена.", "services": kb.services_text()}
    _, _, duration = service

    day = day.replace(minute=0, second=0, microsecond=0)
    open_dt = day.replace(hour=kb.OPEN_HOUR)
    close_dt = day.replace(hour=kb.CLOSE_HOUR)
    now = _today()

    existing = db.get_bookings_for_day(day.strftime("%Y-%m-%d"))
    busy = [(datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"])) for b in existing]

    slots = []
    step = timedelta(minutes=kb.SLOT_STEP_MINUTES)
    cur = open_dt
    while cur + timedelta(minutes=duration) <= close_dt:
        slot_end = cur + timedelta(minutes=duration)
        conflict = _in_lunch(cur, slot_end) or cur < now
        for bs, be in busy:
            if cur < be and slot_end > bs:
                conflict = True
                break
        if not conflict:
            slots.append(cur.strftime("%H:%M"))
        cur += step

    return {
        "ok": True,
        "date": day.strftime("%Y-%m-%d"),
        "service": service[0],
        "slots": slots,
        "work_hours": f"{kb.OPEN_HOUR:02d}:00-{kb.CLOSE_HOUR:02d}:00",
        "lunch": f"{kb.LUNCH_START_HOUR:02d}:00-{kb.LUNCH_END_HOUR:02d}:00",
    }


def create_booking(chat_id: int, date_str: str, time_str: str, service_name: str,
                   client_name: str, client_phone: str) -> dict:
    """Создаёт запись, если слот свободен."""
    day = parse_date(date_str)
    if day is None:
        return {"ok": False, "error": "Не удалось распознать дату."}

    service = kb.find_service(service_name)
    if service is None:
        return {"ok": False, "error": f"Услуга «{service_name}» не найдена."}
    name, price, duration = service

    try:
        hh, mm = map(int, time_str.strip().split(":"))
    except ValueError:
        return {"ok": False, "error": "Не удалось распознать время. Укажите в формате ЧЧ:ММ."}

    start = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
    end = start + timedelta(minutes=duration)

    open_dt = start.replace(hour=kb.OPEN_HOUR, minute=0)
    close_dt = start.replace(hour=kb.CLOSE_HOUR, minute=0)
    if start < open_dt or end > close_dt:
        return {"ok": False, "error": f"Время вне часов работы ({kb.OPEN_HOUR:02d}:00-{kb.CLOSE_HOUR:02d}:00)."}
    if _in_lunch(start, end):
        return {"ok": False, "error": f"Это время попадает на перерыв ({kb.LUNCH_START_HOUR:02d}:00-{kb.LUNCH_END_HOUR:02d}:00)."}
    if start < _today():
        return {"ok": False, "error": "Нельзя записаться на прошедшее время."}
    if db.has_overlap(start.isoformat(), end.isoformat()):
        return {"ok": False, "error": "Это время уже занято. Выберите другой слот."}
    if not client_name or not client_phone:
        return {"ok": False, "error": "Нужны имя и номер телефона клиента."}

    booking_id = db.add_booking(
        chat_id, name, start.isoformat(), end.isoformat(), client_name, client_phone
    )
    return {
        "ok": True,
        "booking_id": booking_id,
        "service": name,
        "price": price,
        "date": start.strftime("%Y-%m-%d"),
        "time": start.strftime("%H:%M"),
        "client_name": client_name,
        "client_phone": client_phone,
    }
