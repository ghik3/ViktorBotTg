import asyncio
import time
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .settings import BOT_TOKEN, ADMIN_ID
from .db import init_db, list_open_tickets, delete_ticket, mark_admin_reminded

# Настройки автоочистки и напоминаний
TICKET_TTL_SEC = 30 * 60          # 30 минут
REMIND_AFTER_SEC = 5 * 60         # первое напоминание через 5 минут
REMIND_EVERY_SEC = 10 * 60        # повтор каждые 10 минут
LOOP_INTERVAL_SEC = 60            # проверка раз в минуту


async def cleanup_and_remind_loop(bot: Bot, admin_id: int):
    while True:
        try:
            now = int(time.time())
            tickets = await list_open_tickets(limit=200)

            for t in tickets:
                tid = t["id"]
                age = now - int(t["created_ts"])

                # 1) автоочистка по TTL
                if age >= TICKET_TTL_SEC:
                    await delete_ticket(tid)
                    # уведомим админа + игрока
                    await bot.send_message(admin_id, f"🧹 Заявка #{tid} удалена (прошло > 30 минут, без закрытия).")
                    await bot.send_message(t["user_id"], f"🧹 Заявка #{tid} была автоматически очищена (прошло > 30 минут). Если актуально — создай новую.")
                    continue

                # 2) напоминания админу: если долго нет ответа админа
                last_reply = t.get("last_admin_reply_ts")
                last_remind = t.get("last_admin_remind_ts") or 0

                # если админ уже отвечал — не напоминаем
                if last_reply is not None:
                    continue

                if age >= REMIND_AFTER_SEC and (now - int(last_remind)) >= REMIND_EVERY_SEC:
                    await bot.send_message(
                        admin_id,
                        f"⏰ Напоминание: заявка #{tid} ждёт ответа.\n"
                        f"От: {t['user_id']}\n"
                        f"Создано: {t['created_at']}"
                    )
                    await mark_admin_reminded(tid, now)

        except Exception as e:
            # чтобы цикл не умер из-за одной ошибки
            try:
                await bot.send_message(admin_id, f"⚠️ Ошибка фонового цикла: {e}")
            except Exception:
                pass

        await asyncio.sleep(LOOP_INTERVAL_SEC)


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp["config"] = {"admin_id": ADMIN_ID}

    from .handlers_user import user_router
    from .handlers_admin import admin_router
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
    import contextlib
    asyncio.run(main())
