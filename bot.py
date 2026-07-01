"""Telegram-бот салона «Стрижка»: точка входа."""
import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import ai_assistant
import config
import database as db
import google_calendar
import keyboards
import knowledge_base as kb

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

GREETING = f'Здравствуйте! Я ваш помощник из салона «{kb.SALON_NAME}». Чем могу помочь?'


def _get_history(context: ContextTypes.DEFAULT_TYPE) -> list:
    history = context.user_data.get("history")
    if history is None:
        history = ai_assistant.build_history()
        context.user_data["history"] = history
    return history


async def _notify_admin(context: ContextTypes.DEFAULT_TYPE, bookings: list) -> None:
    """Отправляет администратору уведомления о новых записях."""
    if not config.ADMIN_CHAT_ID:
        return
    for b in bookings:
        text = (
            "🔔 Новая запись!\n"
            f"Услуга: {b['service']}\n"
            f"Дата: {b['date']} в {b['time']}\n"
            f"Клиент: {b['client_name']}\n"
            f"Телефон: {b['client_phone']}"
        )
        try:
            await context.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=text)
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось отправить уведомление администратору")


async def _ask_llm(history: list, text: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    try:
        answer, created = await asyncio.to_thread(ai_assistant.reply, history, text, chat_id)
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка при обращении к LLM")
        return "Извините, произошла техническая ошибка. Попробуйте ещё раз чуть позже."
    if created:
        await _notify_admin(context, created)
    return answer


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["history"] = ai_assistant.build_history()
    await update.message.reply_text(GREETING, reply_markup=keyboards.main_menu())


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["history"] = ai_assistant.build_history()
    await update.message.reply_text("Диалог сброшен. Чем могу помочь?", reply_markup=keyboards.main_menu())


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    now_iso = datetime.now(config.TZ).isoformat()
    rows = db.get_upcoming_bookings(chat_id, now_iso)
    if not rows:
        await update.message.reply_text("У вас пока нет активных записей.")
        return
    await update.message.reply_text("Ваши записи:")
    for b in rows:
        start = datetime.fromisoformat(b["start"])
        text = f"• {b['service']} — {start.strftime('%Y-%m-%d')} в {start.strftime('%H:%M')}"
        await update.message.reply_text(text, reply_markup=keyboards.cancel_inline(b["id"]))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    chat_id = update.effective_chat.id

    # Быстрые ответы на кнопки нижнего меню (без обращения к LLM).
    if text == keyboards.BTN_HOURS:
        await update.message.reply_text(kb.hours_text())
        return
    if text == keyboards.BTN_CONTACTS:
        await update.message.reply_text(kb.contacts_text())
        return
    if text == keyboards.BTN_SERVICES:
        await update.message.reply_text("Наши услуги:\n" + kb.services_text())
        return
    if text == keyboards.BTN_MY_BOOKINGS:
        await my_bookings(update, context)
        return
    if text == keyboards.BTN_BOOK:
        await update.message.reply_text(
            "Выберите услугу для записи:", reply_markup=keyboards.services_inline()
        )
        return

    history = _get_history(context)
    answer = await _ask_llm(history, text, chat_id, context)
    await update.message.reply_text(answer)


async def on_service_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    key = query.data.split(":", 1)[1]
    service = kb.SERVICES.get(key)
    if service is None:
        await query.edit_message_text("Услуга не найдена. Попробуйте ещё раз.")
        return
    name = service[0]

    await query.edit_message_text(f"Записываю на «{name}».")

    history = _get_history(context)
    chat_id = update.effective_chat.id
    answer = await _ask_llm(history, f"Хочу записаться на услугу «{name}».", chat_id, context)
    await context.bot.send_message(chat_id=chat_id, text=answer)


async def on_cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    booking_id = int(query.data.split(":", 1)[1])
    row = db.get_booking(booking_id, chat_id)
    if row is None:
        await query.edit_message_text("Запись не найдена или уже отменена.")
        return

    if row.get("gcal_event_id"):
        google_calendar.delete_event(row["gcal_event_id"])
    db.delete_booking(booking_id, chat_id)

    start = datetime.fromisoformat(row["start"])
    await query.edit_message_text(
        f"Запись отменена: {row['service']} — {start.strftime('%Y-%m-%d')} в {start.strftime('%H:%M')}."
    )

    if config.ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_CHAT_ID,
                text=(
                    "❌ Отмена записи!\n"
                    f"Услуга: {row['service']}\n"
                    f"Было: {start.strftime('%Y-%m-%d')} в {start.strftime('%H:%M')}\n"
                    f"Клиент: {row.get('client_name')}"
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось уведомить администратора об отмене")


def main() -> None:
    config.validate()
    db.init_db()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("mybookings", my_bookings))
    app.add_handler(CallbackQueryHandler(on_service_chosen, pattern=r"^book:"))
    app.add_handler(CallbackQueryHandler(on_cancel_booking, pattern=r"^cancel:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен. Ожидание сообщений...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
