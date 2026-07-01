"""Клавиатуры Telegram: нижнее меню и инлайн-выбор услуги."""
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

import knowledge_base as kb

# Подписи кнопок нижнего меню (используются и при обработке нажатий).
BTN_SERVICES = "✂️ Услуги и цены"
BTN_HOURS = "🕐 Часы работы"
BTN_BOOK = "📅 Записаться"
BTN_CONTACTS = "📍 Адрес и контакты"


def main_menu() -> ReplyKeyboardMarkup:
    """Постоянное нижнее меню с основными действиями."""
    return ReplyKeyboardMarkup(
        [
            [BTN_SERVICES, BTN_HOURS],
            [BTN_BOOK, BTN_CONTACTS],
        ],
        resize_keyboard=True,
    )


def services_inline() -> InlineKeyboardMarkup:
    """Инлайн-кнопки выбора услуги для записи (callback_data = 'book:<ключ>')."""
    rows = []
    for key, (name, price, _minutes) in kb.SERVICES.items():
        rows.append([InlineKeyboardButton(f"{name} — {price} ₽", callback_data=f"book:{key}")])
    return InlineKeyboardMarkup(rows)
