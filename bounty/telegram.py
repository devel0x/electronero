#!/usr/bin/env python3
import os
import time
import json
import logging
from typing import Optional, Dict, Any, Iterable

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models import Base, TelegramUser  # <-- make sure TelegramUser is defined in your models.py (Option 1)
# from app.database import Base  # if you keep Base there instead


# -------------------------
# Config & Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("telegram_poller")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
OFFSET_FILE = os.getenv("TG_OFFSET_FILE", ".telegram_offset")
POLL_SLEEP = int(os.getenv("TG_POLL_SLEEP", "2"))  # seconds between polls

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# SQLAlchemy session
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Make sure tables exist (safe if you already did migrations)
Base.metadata.create_all(bind=engine)


# -------------------------
# Helpers
# -------------------------
def read_offset() -> Optional[int]:
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


def write_offset(offset: int) -> None:
    try:
        with open(OFFSET_FILE, "w") as f:
            f.write(str(offset))
    except Exception as e:
        logger.warning("Failed to write offset file: %s", e)


def upsert_telegram_user(session: Session, tg_user: Dict[str, Any]) -> None:
    """
    Insert or update TelegramUser in DB.
    Assumes TelegramUser model exists:
        class TelegramUser(Base):
            __tablename__ = "telegram_users"
            user_id = Column(Integer, primary_key=True, autoincrement=False)
            username = Column(String(100), unique=True, index=True)
            first_name = Column(String(100), nullable=True)
            last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    """
    if not tg_user or "id" not in tg_user:
        return

    user_id = tg_user["id"]
    username = tg_user.get("username")
    first_name = tg_user.get("first_name")

    existing = session.query(TelegramUser).filter_by(user_id=user_id).first()
    if existing:
        existing.username = username
        existing.first_name = first_name
        # last_seen will auto-update w/ onupdate
    else:
        session.add(
            TelegramUser(
                user_id=user_id,
                username=username,
                first_name=first_name,
            )
        )
    session.commit()
    logger.info("Upserted Telegram user %s (%s)", username, user_id)


def iter_possible_froms(update: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """
    Yield possible 'from' dicts out of a Telegram update.
    Handles message, edited_message, callback_query, my_chat_member, chat_member, etc.
    """
    if "message" in update and "from" in update["message"]:
        yield update["message"]["from"]
    if "edited_message" in update and "from" in update["edited_message"]:
        yield update["edited_message"]["from"]
    if "callback_query" in update and "from" in update["callback_query"]:
        yield update["callback_query"]["from"]
    if "my_chat_member" in update and "from" in update["my_chat_member"]:
        yield update["my_chat_member"]["from"]
    if "chat_member" in update and "from" in update["chat_member"]:
        yield update["chat_member"]["from"]


def poll_forever():
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    offset = read_offset()
    logger.info("Starting telegram poller with offset=%s", offset)

    # Set a long read timeout (e.g., 35 seconds)
    with httpx.Client(timeout=httpx.Timeout(40.0)) as client:
        while True:
            try:
                # Use a long polling timeout for Telegram
                params = {"timeout": 30}
                if offset is not None:
                    params["offset"] = offset

                resp = client.get(f"{base_url}/getUpdates", params=params)
                data = resp.json()

                if not data.get("ok"):
                    logger.warning("getUpdates returned not ok: %s", data)
                    time.sleep(POLL_SLEEP)
                    continue

                results = data.get("result", [])
                if not results:
                    # nothing new
                    time.sleep(POLL_SLEEP)
                    continue

                with SessionLocal() as session:
                    for upd in results:
                        offset = upd["update_id"] + 1
                        for frm in iter_possible_froms(upd):
                            upsert_telegram_user(session, frm)

                write_offset(offset)

            except httpx.ReadTimeout:
                # Normal in long polling — just loop again
                logger.debug("No updates, polling again...")
                continue
            except KeyboardInterrupt:
                logger.info("Shutting down poller...")
                break
            except Exception as e:
                logger.exception("Error in poller loop: %s", e)
                time.sleep(POLL_SLEEP)

if __name__ == "__main__":
    poll_forever()

