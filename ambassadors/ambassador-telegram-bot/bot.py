import os
from typing import Dict, Any

import requests
from dotenv import load_dotenv
from redis.asyncio import Redis
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

load_dotenv()

API_BASE = os.getenv("AMBASSADOR_API_BASE", "http://localhost:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Task definitions mirror the web application
TASK_LIST = [
    ("community_building", "Community Building – Invite new members, welcome them, keep chats active."),
    ("content_engagement", "Content Engagement – Post, RT, comment, and boost Interchained/Elara content."),
    ("graphics_media", "Graphics & Media – Memes, banners, infographics, reels, videos, GIFs."),
    ("copywriting", "Copywriting – Threads, blogs, captions that explain ITC/Elara."),
    ("education", "Education – Mini explainers, tutorials, how-to guides."),
    ("spaces_amas", "Spaces & AMAs – Organize or co-host community calls and events."),
    ("moderation_support", "Moderation & Support – Help in TG/Discord, answer questions, guide newcomers."),
    ("regional_growth", "Regional Growth – Promote in your language/region, start local groups."),
    ("creative_campaigns", "Creative Campaigns – Launch challenges, hashtags, or contests."),
    ("advisory_outreach", "Advisory & Partnership Outreach – Introduce new partners, projects, or influencers."),
]
TASK_LABELS = {tid: desc for tid, desc in TASK_LIST}

redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


async def _find_email_by_username(username: str) -> str | None:
    cursor = "0"
    username_norm = username.lower()
    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match="user:*", count=100)
        for key in keys:
            data: Dict[str, Any] = await redis_client.hgetall(key)
            handle = data.get("telegram", "").lstrip("@").lower()
            if handle == username_norm:
                return key.split(":", 1)[1]
        if cursor == "0":
            break
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Welcome to the Ambassador bot! Use /checkin to authenticate.")


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("Please set a Telegram username in your profile.")
        return
    email = await _find_email_by_username(username)
    if not email:
        await update.message.reply_text("Username not registered. Please sign up on the website first.")
        return
    context.user_data["email"] = email
    await update.message.reply_text(f"Checked in as {username}!")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        resp = requests.get(f"{API_BASE}/api/leaderboard.json", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        lines = [f"{row['name']} – {row['points']}" for row in data.get("rows", [])[:10]]
        text = "Top Ambassadors:\n" + "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        text = f"Failed to fetch leaderboard: {exc}"
    await update.message.reply_text(text)


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    email = context.user_data.get("email")
    if not email:
        await update.message.reply_text("Use /checkin first.")
        return
    statuses = await redis_client.hgetall(f"tasks:{email}")
    lines = []
    for tid, desc in TASK_LIST:
        status = statuses.get(tid, "open")
        lines.append(f"{tid} – {status}")
    await update.message.reply_text("\n".join(lines))


async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    email = context.user_data.get("email")
    if not email:
        await update.message.reply_text("Use /checkin first.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /apply <task_id>")
        return
    task_id = context.args[0]
    if task_id not in TASK_LABELS:
        await update.message.reply_text("Unknown task id.")
        return
    await redis_client.hset(f"tasks:{email}", task_id, "applied")
    await update.message.reply_text(f"Applied for {task_id}.")


async def submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    email = context.user_data.get("email")
    if not email:
        await update.message.reply_text("Use /checkin first.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /submit <url>")
        return
    url = context.args[0].strip()
    if not url:
        await update.message.reply_text("Invalid URL.")
        return
    await redis_client.lpush(f"posts:{email}", url)
    await update.message.reply_text("Post submitted for verification.")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("apply", apply))
    application.add_handler(CommandHandler("submit", submit))
    application.run_polling()


if __name__ == "__main__":
    main()
