from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is empty in .env")

    admin_id_raw = os.getenv("ADMIN_ID", "").strip()
    if not admin_id_raw.isdigit():
        raise RuntimeError("ADMIN_ID is empty or invalid in .env")

    return Config(bot_token=token, admin_id=int(admin_id_raw))
