import asyncio
import time
import contextlib

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# ✅ Работает и при запуске "python -m app.main", и при "python app/main.py"
try:
    from .settings import BOT_TOKEN, ADMIN_ID
    from .db import init_db, list_open_tickets, delete_ticket, mark_admin_reminded
    from .handlers_user import user_router
    from .handlers_admin import admin_router
except ImportError:
    from settings import BOT_TOKEN, ADMIN_ID
    from db import init_db, list_open_tickets, delete_ticket, mark_admin_reminded
    from handlers_user import user_router
    from handlers_admin import admin_router


# Настройки автоочистки и напоминаний
TICKET_TTL_SEC = 30 * 60
REMIND_AFTER_SEC = 5 * 60
REMIND_EVERY_SEC = 10 * 60
LOOP_INTERVAL_SEC = 60


async def cleanup_and_remind_loop(bot: Bot, admin_id: int):
    while True:
        try:
            now = int(time.time())
            tickets = await list_open_tickets(limit=200)

            for t in tickets:
                tid = t["id"]
                age = now - int(t["created_ts"])

                # автоочистка тикетов старше 30 минут
                if age >= TICKET_TTL_SEC:
                    await delete_ticket(tid)
                    try:
                        await bot.send_message(admin_id, f"🧹 Заявка #{tid} удалена (прошло > 30 минут).")
                        await bot.send_message(
                            t["user_id"],
                            f"🧹 Заявка #{tid} была автоматически очищена (прошло > 30 минут). Если актуально — создай новую."
                        )
                    except Exception:
                        pass
                    continue

                # напоминания админу, если он не отвечал
                last_reply = t.get("last_admin_reply_ts")
                last_remind = t.get("last_admin_remind_ts") or 0

                if last_reply is not None:
                    continue

                if age >= REMIND_AFTER_SEC and (now - int(last_remind)) >= REMIND_EVERY_SEC:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"⏰ Напоминание: заявка #{tid} ждёт ответа.\n"
                            f"От: {t['user_id']}\n"
                            f"Создано: {t['created_at']}"
                        )
                        await mark_admin_reminded(tid, now)
                    except Exception:
                        pass

        except Exception as e:
            print(f"[BACKGROUND_ERROR] {e}")

        await asyncio.sleep(LOOP_INTERVAL_SEC)


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp["config"] = {"admin_id": ADMIN_ID}

    dp.include_router(user_router)
    dp.include_router(admin_router)

    bg_task = asyncio.create_task(cleanup_and_remind_loop(bot, ADMIN_ID))

    try:
        await dp.start_polling(bot)
    finally:
        bg_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await bg_task


if __name__ == "__main__":
    asyncio.run(main())
