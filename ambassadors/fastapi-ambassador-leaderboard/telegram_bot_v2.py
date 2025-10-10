import logging
import os
import re
from html import escape
from typing import Dict, Optional, Set

import httpx
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from main import TASK_LIST, REGISTERED_EMAILS, _hash_password, _normalize_telegram, redis_client, _get_cached_data

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HASHRATE_API = "https://explorer.interchained.org/api/mining/hashrate"

# Conversation states
WAITING_EMAIL = 0
WAITING_PASSWORD = 1
WAITING_REG_PASSWORD = 2
WAITING_REG_TELEGRAM = 3
WAITING_REG_WALLET = 4
WAITING_NEW_WALLET = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- MENU SYSTEM --------------------

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an interactive main menu."""
    keyboard = [
        [InlineKeyboardButton("📋 Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("💼 Apply for Task", callback_data="menu_apply")],
        [InlineKeyboardButton("✅ Verify Submission", callback_data="menu_verify")],
        [InlineKeyboardButton("💳 Update Wallet", callback_data="menu_wallet")],
        [InlineKeyboardButton("📊 Network Hashrate", callback_data="menu_hashrate")],
        [InlineKeyboardButton("🚪 Logout", callback_data="menu_logout")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👇 Choose an action:", reply_markup=reply_markup)

async def on_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu selections."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    # Map menu choices to commands
    if choice == "menu_tasks":
        await tasks(update, context)
    elif choice == "menu_leaderboard":
        await leaderboard(update, context)
    elif choice == "menu_apply":
        await query.message.reply_text("Use /apply <task_id> to apply for a task.")
    elif choice == "menu_verify":
        await query.message.reply_text("Use /verify <url> to submit your content for verification.")
    elif choice == "menu_wallet":
        await wallet_start(update, context)
    elif choice == "menu_hashrate":
        await hashrate(update, context)
    elif choice == "menu_logout":
        await logout(update, context)
    else:
        await query.message.reply_text("❓ Unknown option.")

# -------------------- AUTH & COMMANDS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await menu(update, context)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await menu(update, context)

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
                "I can’t DM you yet. Please open this bot in a private chat and press /start, then run /checkin again there."
            )
            return ConversationHandler.END

    await update.message.reply_text("🔒 Please enter your *email*:", parse_mode="Markdown")
    return WAITING_EMAIL

async def received_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = (update.message.text or "").strip().lower()
    context.user_data["email"] = email
    if email not in REGISTERED_EMAILS:
        await update.message.reply_text("This email isn’t registered. Contact an admin.")
        return ConversationHandler.END
    await update.message.reply_text("✅ Email received. Now enter your *password*:", parse_mode="Markdown")
    return WAITING_PASSWORD

# (rest of registration / authentication logic unchanged...)

# -------------------- UTILS --------------------

def _parse_admin_ids(raw: str) -> Set[int]:
    ids: Set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            logger.warning("Ignoring invalid TELEGRAM_ADMIN_IDS entry: %s", part)
    return ids

def _parse_admin_usernames(raw: str) -> Set[str]:
    handles: Set[str] = set()
    for part in raw.split(","):
        handle = _normalize_telegram(part)
        if handle:
            handles.add(handle)
    return handles

ADMIN_USER_IDS: Set[int] = _parse_admin_ids(os.getenv("TELEGRAM_ADMIN_IDS", ""))
ADMIN_USERNAMES: Set[str] = _parse_admin_usernames(os.getenv("TELEGRAM_ADMIN_USERNAMES", ""))

def _is_admin_user(user: Optional[User]) -> bool:
    if user is None:
        return False
    if ADMIN_USER_IDS and user.id in ADMIN_USER_IDS:
        return True
    username = _normalize_telegram(getattr(user, "username", ""))
    return ADMIN_USERNAMES and username in ADMIN_USERNAMES

# (rest of task handling, verify, leaderboard, pump, hashrate functions unchanged...)

# -------------------- ERROR HANDLER --------------------

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Update caused error: %s", context.error)

# -------------------- ENTRYPOINT --------------------

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    application = Application.builder().token(BOT_TOKEN).build()

    # Conversations
    conv = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin)],
        states={
            WAITING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_email)
            ],
            WAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_password)
            ],
        },
        fallbacks=[],
        per_chat=False,
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CallbackQueryHandler(on_menu_choice))
    application.add_handler(conv)
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("apply", apply_task))
    application.add_handler(CommandHandler("verify", verify))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("pump", pump))
    application.add_handler(CommandHandler("hashrate", hashrate))
    application.add_handler(CommandHandler("logout", logout))
    application.add_error_handler(on_error)

    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
