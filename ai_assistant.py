"""ИИ-ассистент салона на базе GigaChat (Sber) с function calling для записи."""
import json
from datetime import datetime

from gigachat import GigaChat
from gigachat.models import (
    Chat,
    Function,
    FunctionParameters,
    Messages,
    MessagesRole,
)

import config
import booking
import knowledge_base as kb

_client = GigaChat(
    credentials=config.GIGACHAT_CREDENTIALS,
    scope=config.GIGACHAT_SCOPE,
    model=config.GIGACHAT_MODEL,
    verify_ssl_certs=config.GIGACHAT_VERIFY_SSL,
    ca_bundle_file=config.GIGACHAT_CA_BUNDLE_FILE,
)


def _system_prompt() -> str:
    now = datetime.now(config.TZ)
    return f"""Ты — вежливый ассистент салона красоты «{kb.SALON_NAME}».
Сегодня {now.strftime('%Y-%m-%d')}, текущее время {now.strftime('%H:%M')}.
Салон работает ежедневно с {kb.OPEN_HOUR:02d}:00 до {kb.CLOSE_HOUR:02d}:00, перерыв с {kb.LUNCH_START_HOUR:02d}:00 до {kb.LUNCH_END_HOUR:02d}:00.
Адрес: {kb.SALON_ADDRESS}. Телефон: {kb.SALON_PHONE}.

Услуги и цены:
{kb.services_text()}

Твои задачи:
1. Вести живой, дружелюбный диалог на русском языке, коротко и по делу.
2. Отвечать на вопросы об услугах, ценах и часах работы, опираясь на данные выше.
3. Записывать клиентов на приём.

Правила записи (СТРОГО соблюдай):
- Сначала уточни услугу и желаемую дату/время.
- Чтобы показать свободное время, вызывай функцию get_available_slots.
- Перед подтверждением записи обязательно уточни имя и номер телефона клиента.
- ВАЖНО: НИКОГДА не подтверждай запись словами, пока не вызвал функцию create_booking.
  Запись считается сделанной ТОЛЬКО после успешного вызова create_booking.
  Сообщай «вы записаны» исключительно после того, как функция вернула ok=true.
- После успешного create_booking подтверди детали (услуга, дата, время) и напомни,
  что придёт SMS-напоминание за день до визита.
- Если слот занят или попадает на перерыв — предложи ближайшие свободные варианты.
Не выдумывай услуги и цены, которых нет в списке."""


FUNCTIONS = [
    Function(
        name="get_available_slots",
        description="Получить список свободных слотов на указанный день для услуги.",
        parameters=FunctionParameters(
            type="object",
            properties={
                "date": {"type": "string", "description": "Дата: YYYY-MM-DD, 'сегодня' или 'завтра'."},
                "service": {"type": "string", "description": "Название услуги, например 'Мужская стрижка'."},
            },
            required=["date", "service"],
        ),
    ),
    Function(
        name="create_booking",
        description="Создать запись клиента на приём.",
        parameters=FunctionParameters(
            type="object",
            properties={
                "date": {"type": "string", "description": "Дата: YYYY-MM-DD, 'сегодня' или 'завтра'."},
                "time": {"type": "string", "description": "Время начала в формате ЧЧ:ММ."},
                "service": {"type": "string", "description": "Название услуги."},
                "client_name": {"type": "string", "description": "Имя клиента."},
                "client_phone": {"type": "string", "description": "Телефон клиента."},
            },
            required=["date", "time", "service", "client_name", "client_phone"],
        ),
    ),
]


def _dispatch(name: str, args: dict, chat_id: int, created: list) -> dict:
    if name == "get_available_slots":
        return booking.available_slots(args.get("date", ""), args.get("service", ""))
    if name == "create_booking":
        result = booking.create_booking(
            chat_id,
            args.get("date", ""),
            args.get("time", ""),
            args.get("service", ""),
            args.get("client_name", ""),
            args.get("client_phone", ""),
        )
        if result.get("ok"):
            created.append(result)
        return result
    return {"ok": False, "error": f"Неизвестная функция {name}"}


def build_history() -> list:
    """Создаёт стартовую историю диалога с системным промптом."""
    return [Messages(role=MessagesRole.SYSTEM, content=_system_prompt())]


def reply(history: list, user_text: str, chat_id: int):
    """Обрабатывает сообщение пользователя, при необходимости вызывая функции.

    history мутируется на месте (добавляются реплики пользователя и ассистента).
    Возвращает кортеж (текст_ответа, список_созданных_записей).
    """
    history.append(Messages(role=MessagesRole.USER, content=user_text))
    created: list = []

    for _ in range(5):  # ограничение на число цепочек вызовов функций
        payload = Chat(
            messages=history,
            functions=FUNCTIONS,
            function_call="auto",
            temperature=0.5,
        )
        resp = _client.chat(payload)
        msg = resp.choices[0].message
        history.append(msg)

        if msg.function_call is None:
            return (msg.content or "Извините, не расслышал. Повторите, пожалуйста.", created)

        fc = msg.function_call
        args = fc.arguments if isinstance(fc.arguments, dict) else {}
        result = _dispatch(fc.name, args, chat_id, created)
        history.append(
            Messages(
                role=MessagesRole.FUNCTION,
                name=fc.name,
                content=json.dumps(result, ensure_ascii=False),
            )
        )

    return ("Извините, не удалось обработать запрос. Попробуйте переформулировать.", created)
