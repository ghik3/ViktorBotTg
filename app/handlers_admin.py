from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
import time

from .support_bridge import ADMIN_MSG_TO_TICKET
from .db import get_ticket, delete_ticket, mark_admin_replied

admin_router = Router()

def is_admin(user_id: int, config) -> bool:
    return user_id == config["admin_id"]

# ✅ Админ отвечает игроку простым Reply на сообщение с заявкой
@admin_router.message(F.reply_to_message)
async def admin_reply_via_reply(message: Message, bot, config):
    if not is_admin(message.from_user.id, config):
        return

    replied = message.reply_to_message
    tid = ADMIN_MSG_TO_TICKET.get(replied.message_id)
    if not tid:
        return  # это не заявка

    ticket = await get_ticket(tid)
    if not ticket:
        await message.answer("❌ Заявка уже удалена/очищена.")
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Напиши текст ответа сообщением 🙂")
        return

    await bot.send_message(ticket["user_id"], f"✉️ Ответ по заявке #{tid}:\n\n{text}")
    await mark_admin_replied(tid, int(time.time()))
    await message.answer(f"✅ Отправлено игроку (заявка #{tid}).")

# ✅ Кнопки: закрыть/удалить
@admin_router.callback_query(F.data.startswith(("tclose:", "tdelete:")))
async def admin_ticket_actions(c: CallbackQuery, bot, config):
    if not is_admin(c.from_user.id, config):
        await c.answer("Нет доступа", show_alert=True)
        return

    action, tid_str = c.data.split(":")
    tid = int(tid_str)

    ticket = await get_ticket(tid)
    ok = await delete_ticket(tid)

    if not ok:
        await c.answer("Уже удалено", show_alert=True)
        return

    if action == "tclose" and ticket:
        try:
            await bot.send_message(ticket["user_id"], f"✅ Ваша заявка #{tid} закрыта. Спасибо!")
        except Exception as e:
            print(f"[USER_SEND_ERROR] {e}")

    # убираем кнопки и показываем результат
    try:
        await c.message.edit_text(f"✅ Готово: заявка #{tid} {'закрыта' if action == 'tclose' else 'удалена'}.")
    except Exception:
        pass

    await c.answer()
