import logging
import os
from typing import Dict

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from main import TASK_LIST, REGISTERED_EMAILS, _hash_password, redis_client

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Conversation states
WAITING_PASSWORD = 1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user."""
    await update.message.reply_text(
        "Welcome to the Ambassador bot. Use /checkin <email> to log in."
    )


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start login by accepting email."""
    if not context.args:
        await update.message.reply_text("Usage: /checkin <email>")
        return ConversationHandler.END
    email = context.args[0].strip().lower()
    context.user_data["email"] = email
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "I'm DMing you to lock in your login \U0001f512"
        )
        await context.bot.send_message(
            chat_id=update.effective_user.id, text="Please enter your password:"
        )
    else:
        await update.message.reply_text("Please enter your password:")
    return WAITING_PASSWORD


async def received_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle password, authenticate against main.py storage."""
    password = update.message.text
    email = context.user_data.get("email", "")
    if email not in REGISTERED_EMAILS:
        await update.message.reply_text("Email not registered. Try again.")
        return ConversationHandler.END
    stored = await redis_client.hgetall(f"user:{email}")
    if not stored or stored.get("password") != _hash_password(password):
        await update.message.reply_text("Invalid credentials.")
        return ConversationHandler.END
    context.user_data["authenticated"] = True
    await update.message.reply_text("Logged in successfully.")
    return ConversationHandler.END


async def ensure_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("authenticated"):
        await update.message.reply_text("Please /checkin first.")
        return False
    return True


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    email = context.user_data.get("email")
    statuses: Dict[str, str] = await redis_client.hgetall(f"tasks:{email}")
    lines = []
    for tid, desc in TASK_LIST:
        status = statuses.get(tid, "pending")
        lines.append(f"{tid}: {status}\n{desc}")
    await update.message.reply_text("\n\n".join(lines))


async def apply_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /apply <task_id>")
        return
    task_id = context.args[0]
    valid_ids = {tid for tid, _ in TASK_LIST}
    if task_id not in valid_ids:
        await update.message.reply_text("Unknown task id.")
        return
    email = context.user_data.get("email")
    await redis_client.hset(f"tasks:{email}", task_id, "applied")
    await update.message.reply_text("Task applied.")


async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /verify <url>")
        return
    url = context.args[0].strip()
    email = context.user_data.get("email")
    await redis_client.lpush(f"posts:{email}", url)
    await update.message.reply_text("Post submitted for verification.")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE_URL}/api/leaderboard.json")
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Failed to fetch leaderboard: {exc}")
        return
    rows = data.get("rows", [])[:5]
    lines = ["Top leaderboard:"]
    for row in rows:
        lines.append(f"{row.get('rank')}. {row.get('name')} - {row.get('points')} pts")
    await update.message.reply_text("\n".join(lines))


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    application = (
        Application.builder().token(BOT_TOKEN).build()
    )
    conv = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin)],
        states={
            WAITING_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    received_password,
                )
            ]
        },
        fallbacks=[],
        per_chat=False,
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv)
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("apply", apply_task))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.wait()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
