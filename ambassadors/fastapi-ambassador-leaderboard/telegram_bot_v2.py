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

# ──────────────────────────────────────────────────────────────
# 🔐 AUTH FLOW
# ──────────────────────────────────────────────────────────────

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

async def received_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = (update.message.text or "").strip()
    email = context.user_data.get("email", "")

    if not email:
        await update.message.reply_text("Session expired. Please /checkin again.")
        return ConversationHandler.END

    stored = await redis_client.hgetall(f"user:{email}")
    if not stored or stored.get("password") != _hash_password(password):
        await update.message.reply_text("❌ Invalid credentials.")
        return ConversationHandler.END

    context.user_data["authenticated"] = True
    await update.message.reply_text("✅ Logged in successfully!")
    return ConversationHandler.END

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text("🔓 Logged out. Use /checkin to log in again.")

async def ensure_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("authenticated"):
        await update.message.reply_text("🔒 Please /checkin first.")
        return False
    return True

async def pump(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin_user(update.effective_user):
        await update.message.reply_text("🚫 Admins only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /pump @username <amount>")
        return

    target = context.args[0]
    amount = float(context.args[1])
    matches = await _emails_for_target(target)
    if not matches:
        await update.message.reply_text(f"Could not find ambassador for {target}.")
        return

    email = matches[0]
    new_total = await redis_client.hincrbyfloat("score_pad", email, amount)
    await redis_client.delete("leaderboard_cache")

    await update.message.reply_text(
        f"✅ Added {amount} points to {target} ({email}). New total: {new_total}."
    )

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await ensure_login(update, context):
        return ConversationHandler.END
    await update.message.reply_text("💼 Please enter your new wallet address:")
    return WAITING_NEW_WALLET

async def wallet_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wallet = update.message.text.strip()
    email = context.user_data.get("email")
    if not email:
        await update.message.reply_text("⚠️ No email found. Please /checkin again.")
        return ConversationHandler.END
    await redis_client.hset(f"user:{email}", mapping={"wallet": wallet})
    await update.message.reply_text("✅ Wallet updated.")
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────
# 📝 REGISTRATION FLOW
# ──────────────────────────────────────────────────────────────

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin registration by collecting email."""
    if update.effective_chat.type != "private":
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="📬 Please DM me your email to start registration."
            )
            await update.message.reply_text("✅ Check your DMs to continue.")
        except Forbidden:
            await update.message.reply_text("I couldn’t DM you. Please message me directly.")
        return ConversationHandler.END

    if not context.args:
        await update.message.reply_text("✉️ Usage: /register <email>")
        return ConversationHandler.END

    email = context.args[0].strip().lower()
    if email not in REGISTERED_EMAILS:
        await update.message.reply_text("🚫 Email not permitted. Contact an admin.")
        return ConversationHandler.END

    exists = await redis_client.exists(f"user:{email}")
    if exists:
        await update.message.reply_text("⚠️ Email already registered.")
        return ConversationHandler.END

    context.user_data["reg_email"] = email
    await update.message.reply_text("🔑 Great! Please choose a password:")
    return WAITING_REG_PASSWORD

async def received_reg_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reg_password"] = update.message.text.strip()
    await update.message.reply_text("📱 Please enter your Telegram username (with or without @):")
    return WAITING_REG_TELEGRAM

async def received_reg_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    username = update.message.text.strip()
    if "http" in username or "t.me" in username:
        await update.message.reply_text("❌ Please enter a username, not a link.")
        return WAITING_REG_TELEGRAM

    context.user_data["reg_telegram"] = _normalize_telegram(username)
    await update.message.reply_text("💼 Finally, please enter your wallet address:")
    return WAITING_REG_WALLET

async def received_reg_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wallet = update.message.text.strip()
    email = context.user_data.get("reg_email")
    password = context.user_data.get("reg_password")
    telegram = context.user_data.get("reg_telegram")

    if not email or not password:
        await update.message.reply_text("⚠️ Registration data missing. Start over with /register.")
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
    await update.message.reply_text("✅ Registration complete! You’re now logged in.")
    return ConversationHandler.END

# ──────────────────────────────────────────────────────────────
# 📋 TASK COMMANDS
# ──────────────────────────────────────────────────────────────

async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    email = context.user_data.get("email")
    statuses: Dict[str, str] = await redis_client.hgetall(f"tasks:{email}")

    lines = []
    for tid, desc in TASK_LIST:
        status = statuses.get(tid, "available")
        lines.append(f"*{tid}*: {status}\n{desc}")
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def apply_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_login(update, context):
        return
    if not context.args:
        await update.message.reply_text("Usage: /apply <task_id>")
        return
    task_id = context.args[0].strip()
    valid_ids = {tid for tid, _ in TASK_LIST}
    if task_id not in valid_ids:
        await update.message.reply_text("⚠️ Unknown task ID.")
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

    pending = await redis_client.lrange(f"posts:{email}", 0, -1)
    verified = await redis_client.smembers(f"posts_verified:{email}")
    if url in pending or url in verified:
        await update.message.reply_text("⚠️ Already submitted.")
        return

    await redis_client.lpush(f"posts:{email}", url)
    await update.message.reply_text("🧾 Post submitted for verification.")

# ──────────────────────────────────────────────────────────────
# 🏆 LEADERBOARD / ADMIN
# ──────────────────────────────────────────────────────────────

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

    text_lines = ["<b>🏆 Top Ambassadors</b>"]
    for row in rows:
        rank = escape(str(row.get("rank", "")))
        name = escape(str(row.get("name", "Unknown")))
        pts = escape(str(row.get("points", 0)))
        text_lines.append(f"{rank}. <b>{name}</b> — {pts} pts")

    await update.message.reply_text("\n".join(text_lines), parse_mode="HTML")

async def hashrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(HASHRATE_API)
            resp.raise_for_status()
            data = resp.json().get("1Day", {})
        val = data.get("val")
        unit = data.get("unitAbbreviation") or data.get("unit")
        if val is None or not unit:
            raise ValueError("unexpected API response")
        message = f"24h average network hashrate: {val} {unit}/s"
    except Exception as exc:
        message = f"Failed to fetch hashrate: {exc}"
    await update.message.reply_text(message)

# ──────────────────────────────────────────────────────────────
# 🧭 MENU SYSTEM
# ──────────────────────────────────────────────────────────────

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main menu with login state awareness."""
    logged_in = "✅ Logged in" if context.user_data.get("authenticated") else "🔒 Not logged in"

    keyboard = [
        [InlineKeyboardButton("📋 Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("💼 Apply for Task", callback_data="menu_apply")],
        [InlineKeyboardButton("✅ Verify Submission", callback_data="menu_verify")],
        [InlineKeyboardButton("📊 Network Hashrate", callback_data="menu_hashrate")],
        [InlineKeyboardButton("🚪 Logout", callback_data="menu_logout")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"⚙️ Ambassador Dashboard\nStatus: {logged_in}\n👇 Choose an action:", reply_markup=reply_markup)

async def on_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "menu_tasks":
        await tasks(update, context)
    elif choice == "menu_leaderboard":
        await leaderboard(update, context)
    elif choice == "menu_apply":
        await query.message.reply_text("Use /apply <task_id> to apply.")
    elif choice == "menu_verify":
        await query.message.reply_text("Use /verify <url> to submit.")
    elif choice == "menu_hashrate":
        await hashrate(update, context)
    elif choice == "menu_logout":
        await logout(update, context)
    else:
        await query.message.reply_text("❓ Unknown option.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await menu(update, context)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await menu(update, context)

# ──────────────────────────────────────────────────────────────
# 🧠 ERROR HANDLER
# ──────────────────────────────────────────────────────────────

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Update caused error: %s", context.error)

# ──────────────────────────────────────────────────────────────
# 🚀 MAIN ENTRYPOINT
# ──────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registration conversation
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            WAITING_REG_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_reg_password)],
            WAITING_REG_TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_reg_telegram)],
            WAITING_REG_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_reg_wallet)],
        },
        fallbacks=[],
        per_chat=False,
    )
    application.add_handler(reg_conv)

    # Login conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("checkin", checkin)],
        states={
            WAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_email)],
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, received_password)],
        },
        fallbacks=[],
        per_chat=False,
    )
    
    # Wallet conversation
    wallet_conv = ConversationHandler(
        entry_points=[CommandHandler("wallet", wallet_start)],
        states={
            WAITING_NEW_WALLET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, wallet_received)
            ],
        },
        fallbacks=[],
        per_chat=False,
    )
    application.add_handler(wallet_conv)


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
    application.add_handler(CommandHandler("hashrate", hashrate))
    application.add_handler(CommandHandler("pump", pump))
    application.add_handler(CommandHandler("logout", logout))
    application.add_error_handler(on_error)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
