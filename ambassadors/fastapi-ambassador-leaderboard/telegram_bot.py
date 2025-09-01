import logging
import os
import re
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

from main import TASK_LIST, REGISTERED_EMAILS, _hash_password, _normalize_telegram, redis_client, _get_cached_data

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Conversation states
WAITING_EMAIL = 0
WAITING_PASSWORD = 1
WAITING_REG_PASSWORD = 2
WAITING_REG_TELEGRAM = 3
WAITING_REG_WALLET = 4
WAITING_NEW_WALLET = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the ITC Governance bot.\n"
        "In DM use /register <email> to sign up /checkin <email> to log in. Then:\n"
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


async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin registration by collecting email."""
    if update.effective_chat.type != "private":
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=(
                    "Let’s get you registered, please use your email address provided on "
                    "the ITC Governance Ambassador form"
                ),
            )
            await update.message.reply_text(
                "I sent you a DM to follow up with your registration."
            )
        except Forbidden:
            await update.message.reply_text(
                "I couldn't DM you. Please message @xChiefMod_bot directly to register."
            )
        return ConversationHandler.END
    if not context.args:
        await update.message.reply_text(
            "Let’s get you registered, please use your email address provided on the ITC Governance Ambassador form"
        )
        return ConversationHandler.END
    email = context.args[0].strip().lower()
    if email not in REGISTERED_EMAILS:
        await update.message.reply_text("Email not permitted.")
        return ConversationHandler.END
    exists = await redis_client.exists(f"user:{email}")
    if exists:
        await update.message.reply_text("Email already registered.")
        return ConversationHandler.END
    context.user_data["reg_email"] = email
    await update.message.reply_text("Please choose a password:")
    return WAITING_REG_PASSWORD


async def received_reg_password(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Store password and ask for wallet."""
    password = update.message.text.strip()
    context.user_data["reg_password"] = password
    await update.message.reply_text("Please enter your wallet address:")
    return WAITING_REG_WALLET

def _normalize_telegram(username: str) -> str:
    username = (username or "").strip()
    if not username:
        return ""
    if username.startswith("@"):
        username = username[1:]
    return username.lower()

async def received_reg_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finalize registration by saving credentials."""
    wallet = update.message.text.strip()
    email = context.user_data.get("reg_email")
    password = context.user_data.get("reg_password")
    if not email or not password:
        await update.message.reply_text(
            "Registration data missing. Start over with /register <email>."
        )
        return ConversationHandler.END
    await redis_client.hset(
        f"user:{email}",
        mapping={
            "password": _hash_password(password),
            "wallet": wallet,
            "telegram": _normalize_telegram(update.effective_user.username or ""),
        },
    )
    context.user_data["authenticated"] = True
    context.user_data["email"] = email
    await update.message.reply_text("Registered successfully.")
    return ConversationHandler.END


async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin registration by collecting email."""
    if update.effective_chat.type != "private":
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=(
                    "Let’s get you registered, please use your email address provided on "
                    "the ITC Governance Ambassador form"
                ),
            )
            await update.message.reply_text(
                "I sent you a DM to follow up with your registration."
            )
        except Forbidden:
            await update.message.reply_text(
                "I couldn't DM you. Please message @xChiefMod_bot directly to register."
            )
        return ConversationHandler.END
    if not context.args:
        await update.message.reply_text(
            "Let’s get you registered, please use your email address provided on the ITC Governance Ambassador form"
        )
        return ConversationHandler.END
    email = context.args[0].strip().lower()
    if email not in REGISTERED_EMAILS:
        await update.message.reply_text("Email not permitted.")
        return ConversationHandler.END
    exists = await redis_client.exists(f"user:{email}")
    if exists:
        await update.message.reply_text("Email already registered.")
        return ConversationHandler.END
    context.user_data["reg_email"] = email
    await update.message.reply_text("Please choose a password:")
    return WAITING_REG_PASSWORD


async def received_reg_password(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Store password and ask for Telegram username."""
    password = update.message.text.strip()
    context.user_data["reg_password"] = password
    await update.message.reply_text(
        "Please enter your Telegram username (with or without @):"
    )
    return WAITING_REG_TELEGRAM


async def received_reg_telegram(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Store Telegram handle and ask for wallet address."""
    username = update.message.text.strip()
    lower = username.lower()
    if re.match(r"https?://", lower) or "t.me/" in lower:
        await update.message.reply_text("Please provide a username, not a URL:")
        return WAITING_REG_TELEGRAM
    context.user_data["reg_telegram"] = _normalize_telegram(username)
    await update.message.reply_text("Please enter your wallet address:")
    return WAITING_REG_WALLET


async def received_reg_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finalize registration by saving credentials."""
    wallet = update.message.text.strip()
    email = context.user_data.get("reg_email")
    password = context.user_data.get("reg_password")
    telegram = context.user_data.get("reg_telegram")
    if not email or not password:
        await update.message.reply_text(
            "Registration data missing. Start over with /register <email>."
        )
        return ConversationHandler.END
    await redis_client.hset(
        f"user:{email}",
        mapping={
            "password": _hash_password(password),
            "wallet": wallet,
            "telegram": telegram or _normalize_telegram(update.effective_user.username or ""),
        },
    )
    context.user_data["authenticated"] = True
    context.user_data["email"] = email
    await update.message.reply_text("Registered successfully.")
    return ConversationHandler.END


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


async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt logged-in users for a new wallet address."""
    if not await ensure_login(update, context):
        return ConversationHandler.END
    if update.effective_chat.type != "private":
        await update.message.reply_text("I'm DMing you to update your wallet address.")
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="Please enter your new wallet address:",
        )
    else:
        await update.message.reply_text("Please enter your new wallet address:")
    return WAITING_NEW_WALLET


async def wallet_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the new wallet for the logged-in user."""
    if not await ensure_login(update, context):
        return ConversationHandler.END
    wallet = update.message.text.strip()
    email = context.user_data.get("email")
    if not email:
        await update.message.reply_text("No email found. Please /checkin again.")
        return ConversationHandler.END
    await redis_client.hset(f"user:{email}", mapping={"wallet": wallet})
    await update.message.reply_text("Wallet updated.")
    return ConversationHandler.END


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
    if not url:
        await update.message.reply_text("Provide a valid URL.")
        return
    pending = await redis_client.lrange(f"posts:{email}", 0, -1)
    verified = await redis_client.smembers(f"posts_verified:{email}")
    if url not in {str(p) for p in pending} and url not in {str(v) for v in verified}:
        await redis_client.lpush(f"posts:{email}", url)
        await update.message.reply_text("🧾 Post submitted for verification.")
    else:
        await update.message.reply_text("⚠️ This link was already submitted.")


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
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            WAITING_REG_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    received_reg_password,
                )
            ],
            WAITING_REG_TELEGRAM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    received_reg_telegram,
                )
            ],
            WAITING_REG_WALLET: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    received_reg_wallet,
                )
            ],
        },
        fallbacks=[],
        per_chat=False,
    )
    application.add_handler(reg_conv)
    wallet_conv = ConversationHandler(
        entry_points=[CommandHandler("wallet", wallet_start)],
        states={
            WAITING_NEW_WALLET: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                    wallet_received,
                )
            ],
        },
        fallbacks=[],
        per_chat=False,
    )
    application.add_handler(wallet_conv)
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
