import aiosqlite
from typing import Optional

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            message TEXT NOT NULL,
            created_ts INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_admin_reply_ts INTEGER,
            last_admin_remind_ts INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_limits (
            user_id INTEGER PRIMARY KEY,
            last_ticket_ts INTEGER NOT NULL DEFAULT 0,
            last_call_ts INTEGER NOT NULL DEFAULT 0
        )
        """)
        await db.commit()


# -------- антиспам --------

async def ensure_user_limits(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_limits (user_id, last_ticket_ts, last_call_ts) VALUES (?, 0, 0)",
            (user_id,)
        )
        await db.commit()

async def get_user_limits(user_id: int) -> dict:
    await ensure_user_limits(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM user_limits WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row)

async def set_last_ticket_ts(user_id: int, ts: int):
    await ensure_user_limits(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_limits SET last_ticket_ts=? WHERE user_id=?", (ts, user_id))
        await db.commit()

async def set_last_call_ts(user_id: int, ts: int):
    await ensure_user_limits(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_limits SET last_call_ts=? WHERE user_id=?", (ts, user_id))
        await db.commit()

async def count_tickets_in_window(user_id: int, from_ts: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM tickets WHERE user_id=? AND created_ts>=?",
            (user_id, from_ts)
        )
        (cnt,) = await cur.fetchone()
        return int(cnt)


# -------- tickets --------

async def create_ticket(user_id: int, username: str | None, message: str, created_ts: int, created_at: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO tickets (user_id, username, status, message, created_ts, created_at)
               VALUES (?, ?, 'open', ?, ?, ?)""",
            (user_id, username, message, created_ts, created_at)
        )
        await db.commit()
        return cur.lastrowid

async def get_ticket(ticket_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def list_open_tickets(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tickets WHERE status='open' ORDER BY id ASC LIMIT ?",
            (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def count_open_tickets() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
        (cnt,) = await cur.fetchone()
        return int(cnt)

async def list_open_ticket_ids(offset: int, limit: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id FROM tickets WHERE status='open' ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = await cur.fetchall()
        return [int(r[0]) for r in rows]

async def mark_admin_replied(ticket_id: int, ts: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tickets SET last_admin_reply_ts=? WHERE id=?", (ts, ticket_id))
        await db.commit()

async def mark_admin_reminded(ticket_id: int, ts: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tickets SET last_admin_remind_ts=? WHERE id=?", (ts, ticket_id))
        await db.commit()

async def delete_ticket(ticket_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
        await db.commit()
        return cur.rowcount > 0

async def delete_all_tickets() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM tickets")
        await db.commit()
        return cur.rowcount

async def delete_expired_tickets(now_ts: int, ttl_sec: int) -> int:
    border = now_ts - ttl_sec
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM tickets WHERE status='open' AND created_ts <= ?", (border,))
        await db.commit()
        return cur.rowcount
