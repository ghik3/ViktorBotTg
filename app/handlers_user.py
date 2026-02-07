from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone
import time

# FIX: двойные импорты (для запуска файлом и модулем)
try:
    from .keyboards import main_menu, back_menu, admin_ticket_kb
    from .support_bridge import ADMIN_MSG_TO_TICKET
    from . import texts
    from .db import (
        create_ticket, get_ticket,
        get_user_limits, set_last_ticket_ts, set_last_call_ts,
        count_tickets_in_window
    )
except ImportError:
    from keyboards import main_menu, back_menu, admin_ticket_kb
    from support_bridge import ADMIN_MSG_TO_TICKET
    import texts
    from db import (
        create_ticket, get_ticket,
        get_user_limits, set_last_ticket_ts, set_last_call_ts,
        count_tickets_in_window
    )

user_router = Router()

TICKET_COOLDOWN_SEC = 60
TICKET_WINDOW_SEC = 600
TICKET_MAX_PER_WINDOW = 3
CALL_COOLDOWN_SEC = 60


class TicketFlow(StatesGroup):
    waiting_text = State()
    waiting_ticket_id = State()


@user_router.message(F.text.in_({"/start", "⬅️ В меню"}))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.WELCOME, parse_mode="Markdown", reply_markup=main_menu())


@user_router.message(F.text == "📚 FAQ")
async def faq(message: Message):
    await message.answer(texts.FAQ, parse_mode="Markdown", reply_markup=back_menu())


@user_router.message(F.text == "📜 Правила")
async def rules(message: Message):
    await message.answer(texts.RULES, parse_mode="Markdown", reply_markup=back_menu())


@user_router.message(F.text == "🆘 Создать обращение")
async def ticket_start(message: Message, state: FSMContext):
    await state.set_state(TicketFlow.waiting_text)
    await message.answer(texts.ASK_TICKET_TEXT, parse_mode="Markdown", reply_markup=back_menu())


@user_router.message(TicketFlow.waiting_text)
async def ticket_text(message: Message, state: FSMContext, bot, config):
    content = (message.text or message.caption or "").strip()
    if not content:
        await message.answer("Напиши текстом, что случилось 🙂", reply_markup=back_menu())
        return

    now = int(time.time())

    limits = await get_user_limits(message.from_user.id)
    if now - int(limits["last_ticket_ts"]) < TICKET_COOLDOWN_SEC:
        wait = TICKET_COOLDOWN_SEC - (now - int(limits["last_ticket_ts"]))
        await message.answer(f"⏳ Подожди {wait} сек и попробуй снова.", reply_markup=main_menu())
        await state.clear()
        return

    cnt = await count_tickets_in_window(message.from_user.id, now - TICKET_WINDOW_SEC)
    if cnt >= TICKET_MAX_PER_WINDOW:
        await message.answer("🚫 Слишком много заявок за короткое время. Попробуй позже.", reply_markup=main_menu())
        await state.clear()
        return

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    ticket_id = await create_ticket(
        user_id=message.from_user.id,
        username=message.from_user.username,
        message=content,
        created_ts=now,
        created_at=created_at
    )
    await set_last_ticket_ts(message.from_user.id, now)

    await state.clear()
    await message.answer(
        texts.TICKET_CREATED.format(ticket_id=ticket_id),
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

    uname = f"@{message.from_user.username}" if message.from_user.username else "(без username)"
    admin_text = (
        f"🆕 Новая заявка #{ticket_id}\n"
        f"От: {message.from_user.id} {uname}\n"
        f"Дата: {created_at}\n\n"
        f"{content}\n\n"
        f"💡 Ответьте на это сообщение (Reply) — бот отправит ответ игроку."
    )

    try:
        sent = await bot.send_message(config["admin_id"], admin_text, reply_markup=admin_ticket_kb(ticket_id))
        ADMIN_MSG_TO_TICKET[sent.message_id] = ticket_id
    except Exception as e:
        print(f"[ADMIN_SEND_ERROR] {e}")


@user_router.message(F.text == "👤 Позвать оператора")
async def call_operator(message: Message, bot, config):
    now = int(time.time())
    limits = await get_user_limits(message.from_user.id)

    if now - int(limits["last_call_ts"]) < CALL_COOLDOWN_SEC:
        wait = CALL_COOLDOWN_SEC - (now - int(limits["last_call_ts"]))
        await message.answer(f"⏳ Подожди {wait} сек и попробуй снова.", reply_markup=main_menu())
        return

    await set_last_call_ts(message.from_user.id, now)

    await message.answer(texts.OPERATOR_CALLED, reply_markup=main_menu())

    uname = f"@{message.from_user.username}" if message.from_user.username else "(без username)"
    text = (
        "📣 Игрок зовёт оператора\n"
        f"ID: {message.from_user.id}\n"
        f"Username: {uname}"
    )

    try:
        await bot.send_message(config["admin_id"], text)
    except Exception as e:
        print(f"[ADMIN_SEND_ERROR] {e}")


@user_router.message(F.text == "📌 Статус заявки")
async def status_start(message: Message, state: FSMContext):
    await state.set_state(TicketFlow.waiting_ticket_id)
    await message.answer("Введи номер заявки (например: `12`)", parse_mode="Markdown", reply_markup=back_menu())


@user_router.message(TicketFlow.waiting_ticket_id, F.text)
async def status_check(message: Message, state: FSMContext):
    raw = message.text.strip().lstrip("#")
    if not raw.isdigit():
        await message.answer("Нужен номер. Пример: `12`", parse_mode="Markdown")
        return

    ticket_id = int(raw)
    ticket = await get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Заявка не найдена (возможно, она уже очищена).", reply_markup=main_menu())
        await state.clear()
        return

    status = "🟢 Открыта" if ticket["status"] == "open" else "⚫️ Закрыта"
    await message.answer(
        texts.STATUS_TEMPLATE.format(
            ticket_id=ticket["id"],
            status=status,
            created_at=ticket["created_at"],
            message=ticket["message"]
        ),
        parse_mode="Markdown",
        reply_markup=main_menu()
    )
    await state.clear()
