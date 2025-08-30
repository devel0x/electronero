import logging
import os
from typing import Dict

import httpx
from telegram import Update
from telegram.error import Forbidden, BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from main import TASK_LIST, REGISTERED_EMAILS, _hash_password, redis_client, _get_cached_data

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Conversation states
WAITING_EMAIL, WAITING_PASSWORD = range(2)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the ITC Governance bot.\n"
        "Use /checkin to log in (in DM). Then:\n"
        "• /tasks – view task statuses\n"
        "• /apply <task_id> – apply to a task\n"
        "• /verify <url> – submit a link for verification\n"
        "• /leaderboard – top 5\n"
        "• /logout – clear your session"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Start login flow. Always move to DM for privacy:
      1) Ask for email (WAITING_EMAIL)
      2) Ask for password (WAITING_PASSWORD)
    """
    # If invoked in a group, try to DM first
    if update.effective_chat.type != "private":
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="🔒 Let's get you logged in. Please enter your *email*:",
                parse_mode="Markdown",
            )
            await update.message.reply_text("🔐 Check your DMs to continue login.")
            return WAITING_EMAIL
        except (Forbidden, BadRequest):
            await update.message.reply_text(
                "I can’t DM you yet. Please open this bot in a private chat and press /start, "
                "then run /checkin again there."
            )
            return ConversationHandler.END

    # If already in a private chat, ask for email
    await update.message.reply_text("🔒 Please enter your *email*:", parse_mode="Markdown")
    return WAITING_EMAIL


async def received_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store email and prompt for password."""
    email = (update.message.text or "").strip().lower()
    context.user_data["email"] = email

    # Light check (don’t reveal list details; just say not registered)
    if email not in REGISTERED_EMAILS:
        await update.message.reply_text(
            "This email isn’t registered. If you believe this is an error, contact an admin."
        )
        # End here to avoid prompting for password for unknown email
        return ConversationHandler.END

    await update.message.reply_text("✅ Email received. Now enter your *password*:", parse_mode="Markdown")
    return WAITING_PASSWORD


async def received_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle password, authenticate against redis-stored hash."""
    password = (update.message.text or "").strip()
    email = context.user_data.get("email", "")

    # If somehow we lost the email state, restart
    if not email:
        await update.message.reply_text("Session expired. Please /checkin again.")
        return ConversationHandler.END

    stored = await redis_client.hgetall(f"user:{email}")
    if not stored or stored.get("password") != _hash_password(password):
        await update.message.reply_text("Invalid credentials.")
        return ConversationHandler.END

    context.user_data["authenticated"] = True
    await update.message.reply_text("✅ Logged in successfully.")
    return ConversationHandler.END


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text("🔓 You’ve been logged out. Use /checkin to login again.")


async def ensure_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("authenticated"):
        # Nudge to DM if they’re in a group
        if update.effective_chat.type != "private":
            await update.message.reply_text("Please DM me and run /checkin to login first.")
        else:
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
        status = statuses.get(tid, "available")
        lines.append(f"*{tid}*: {status}\n{desc}")
    await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True, parse_mode="Markdown")


async def apply_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /apply <task_id>")
        return
    task_id = context.args[0].strip()
    valid_ids = {tid for tid, _ in TASK_LIST}
    if task_id not in valid_ids:
        await update.message.reply_text("Unknown task id.")
        return
    email = context.user_data.get("email")
    await redis_client.hset(f"tasks:{email}", task_id, "applied")
    await update.message.reply_text("✅ Task applied.")


async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /verify <url>")
        return
    url = context.args[0].strip()
    email = context.user_data.get("email")
    if url:
        await redis_client.lpush(f"posts:{email}", url)
        await update.message.reply_text("🧾 Post submitted for verification.")
    else:
        await update.message.reply_text("Provide a valid URL.")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    try:
        data = await _get_cached_data(force_refresh=False)
    except Exception as exc:
        await update.message.reply_text(f"Failed to fetch leaderboard: {exc}")
        return

    rows = data.get("rows", [])[:5]
    if not rows:
        await update.message.reply_text("No leaderboard data yet.")
        return

    lines = ["Top leaderboard:"]
    for row in rows:
        lines.append(f"{row.get('rank')}. {row.get('name')} - {row.get('points')} pts")
    await update.message.reply_text("\n".join(lines), disable_web_page_preview=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Update caused error: %s", context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    application = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin)],
        states={
            WAITING_EMAIL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    received_email,
                )
            ],
            WAITING_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    received_password,
                )
            ],
        },
        fallbacks=[],
        per_chat=False,   # one auth usable in groups too
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(conv)
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("apply", apply_task))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("logout", logout))
    application.add_error_handler(on_error)

    # PTB 20+/21 entrypoint
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

