"""Telegram bot for Ambassadors.

This bot mirrors key features of the ambassador web application by
leveraging its HTTP APIs. Users authenticate with their email address
and password via the FastAPI login endpoint and are mapped to their
Telegram accounts through a small check‑in flow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Path where Telegram ID <-> login info mappings are stored
USERS_FILE = Path(
    os.getenv("TG_USERS_FILE", Path(__file__).with_name("data/telegram_users.json"))
)
# Base URL of the ambassador FastAPI service
API_BASE_URL = os.getenv("AMBASSADOR_API_BASE_URL", "http://localhost:8000")

# Task definitions copied from the ambassador application
TASK_LIST: List[Tuple[str, str]] = [
    ("community_building", "\U0001F539 Community Building – Invite new members, welcome them, keep chats active."),
    ("content_engagement", "\U0001F539 Content Engagement – Post, RT, comment, and boost Interchained/Elara content."),
    ("graphics_media", "\U0001F539 Graphics & Media – Memes, banners, infographics, reels, videos, GIFs."),
    ("copywriting", "\U0001F539 Copywriting – Threads, blogs, captions that explain ITC/Elara."),
    ("education", "\U0001F539 Education – Mini explainers, tutorials, how-to guides."),
    ("spaces_amas", "\U0001F539 Spaces & AMAs – Organize or co-host community calls and events."),
    ("moderation_support", "\U0001F539 Moderation & Support – Help in TG/Discord, answer questions, guide newcomers."),
    ("regional_growth", "\U0001F539 Regional Growth – Promote in your language/region, start local groups."),
    ("creative_campaigns", "\U0001F539 Creative Campaigns – Launch challenges, hashtags, or contests."),
    (
        "advisory_outreach",
        "\U0001F539 Advisory & Partnership Outreach – Introduce new partners, projects, or influencers. Advise on negotiations and decisions.",
    ),
]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def load_users() -> Dict[str, Dict[str, str]]:
    """Load Telegram ID to email/token mappings from USERS_FILE."""
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_users(users: Dict[str, Dict[str, str]]) -> None:
    """Persist mappings to USERS_FILE."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    user_id = str(update.effective_user.id)
    info = users.get(user_id)
    if info:
        await update.message.reply_text(f"Welcome back {info['email']}!")
    else:
        await update.message.reply_text(
            "Welcome! Please check in with /checkin <email> to link your Telegram ID."
        )


def _require_login(update: Update) -> Tuple[str, str] | None:
    """Return (email, token) or prompt the user to check in."""
    users = load_users()
    user_id = str(update.effective_user.id)
    info = users.get(user_id)
    if not info or not info.get("token"):
        if update.message:
            update.message.reply_text("Please /checkin <email> first.")
        return None
    return info["email"], info["token"]


# Pending email awaiting password: Telegram user ID -> email
PENDING_CHECKINS: Dict[str, str] = {}


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Please DM me to /checkin so your password stays private."
        )
        return
    if not context.args:
        await update.message.reply_text("Usage: /checkin <email>")
        return
    email = context.args[0].strip().lower()
    user_id = str(update.effective_user.id)
    PENDING_CHECKINS[user_id] = email
    await update.message.reply_text("Please send your password.")


async def _handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return
    user_id = str(update.effective_user.id)
    email = PENDING_CHECKINS.pop(user_id, None)
    if not email:
        return
    password = update.message.text
    session = requests.Session()
    try:
        resp = session.post(
            f"{API_BASE_URL}/login",
            data={"email": email, "password": password},
            timeout=10,
            allow_redirects=False,
        )
        token = session.cookies.get("session")
        if resp.status_code == 303 and token:
            users = load_users()
            users[user_id] = {"email": email, "token": token}
            save_users(users)
            await update.message.reply_text(
                f"Thanks {email}, you are logged in."
            )
        else:
            await update.message.reply_text(
                "Login failed. Please try /checkin <email> again."
            )
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Login error: {exc}")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display top leaderboard entries from the API."""
    url = f"{API_BASE_URL}/api/leaderboard.json"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        rows = data.get("rows", [])[:10]
        lines = [
            f"{i + 1}. {row.get('name', '?')} - {row.get('points', 0)}"
            for i, row in enumerate(rows)
        ]
        text = "Leaderboard:\n" + "\n".join(lines) if lines else "No leaderboard data found."
    except Exception as exc:  # noqa: BLE001
        text = f"Failed to fetch leaderboard: {exc}"
    await update.message.reply_text(text)


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available ambassador tasks."""
    lines = [f"{tid} – {desc}" for tid, desc in TASK_LIST]
    text = "Available tasks:\n" + "\n".join(lines)
    await update.message.reply_text(text)


async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Submit a task application using the FastAPI endpoint."""
    if not context.args:
        await update.message.reply_text("Usage: /apply <task_id>")
        return
    creds = _require_login(update)
    if not creds:
        return
    email, token = creds
    task_id = context.args[0]
    session = requests.Session()
    session.cookies.set("session", token)
    try:
        resp = session.post(
            f"{API_BASE_URL}/tasks/apply",
            data={"task_id": task_id},
            timeout=10,
        )
        if resp.status_code in {200, 303}:
            msg = "Task application sent."
        else:
            msg = f"Failed to apply (status {resp.status_code})."
    except Exception as exc:  # noqa: BLE001
        msg = f"Error applying for task: {exc}"
    await update.message.reply_text(msg)


async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Submit a post URL for admin verification."""
    if not context.args:
        await update.message.reply_text("Usage: /verify <url>")
        return
    creds = _require_login(update)
    if not creds:
        return
    _email, token = creds
    url_to_verify = context.args[0]
    session = requests.Session()
    session.cookies.set("session", token)
    try:
        resp = session.post(
            f"{API_BASE_URL}/verify",
            data={"url": url_to_verify},
            timeout=10,
        )
        if resp.status_code in {200, 303}:
            msg = "Post submitted for verification."
        else:
            msg = f"Failed to submit post (status {resp.status_code})."
    except Exception as exc:  # noqa: BLE001
        msg = f"Error submitting verification: {exc}"
    await update.message.reply_text(msg)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("apply", apply))
    application.add_handler(CommandHandler("verify", verify))

    # Password handler must come after command handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, _handle_password
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()
