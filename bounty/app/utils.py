"""Task verification helper functions using third‑party APIs."""

import os
import httpx
from sqlalchemy.orm import Session
from . import crud
import logging
from app.models import TelegramUser
from app.database import SessionLocal

# Configure logging (you can adjust level and format)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def resolve_username(username: str, session: Session) -> int | None:
    if not username:
        return None
    handle = username.lstrip("@")
    user = session.query(TelegramUser).filter(
        TelegramUser.username.ilike(handle)
    ).first()
    return user.user_id if user else None

def verify_captcha(token: str) -> bool:
    """Check captcha token using Google reCAPTCHA."""
    if os.getenv("NOCAPTCHA", "false").lower() == "true":
        return True
    secret = os.getenv("CAPTCHA_SECRET")
    if not secret or not token:
        return False
    try:
        resp = httpx.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token},
            timeout=5,
        )
        data = resp.json()
        return data.get("success", False)
    except Exception:
        return False

def verify_telegram(username: str) -> bool:
    """Check if the user has joined the configured Telegram group."""
    logging.info("Verifying Telegram user: %s", username)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    group = os.getenv("TELEGRAM_GROUP_ID")
    logging.debug("TELEGRAM_BOT_TOKEN: %s", "SET" if token else "NOT SET")
    logging.debug("TELEGRAM_GROUP_ID: %s", group)

    if not token or not group or not username:
        logging.warning("Missing required values: token, group, or username.")
        return False

    session = SessionLocal()
    try:
        user_id = resolve_username(username, session)
        logging.info("Resolved username '%s' to user_id: %s", username, user_id)
        if not user_id:
            logging.error("Failed to resolve Telegram username '%s'", username)
            return False
    finally:
        session.close()

    base_url = f"https://api.telegram.org/bot{token}/"
    try:
        resp = httpx.get(
            base_url + "getChatMember",
            params={"chat_id": group, "user_id": user_id},
            timeout=5,
        )
        data = resp.json()
        logging.info("Telegram API Response: %s", data)
        success = resp.status_code == 200 and data.get("ok", False)
        logging.info("Membership check result: %s", success)
        return success
    except Exception as e:
        logging.exception("Error while contacting Telegram API: %s", e)
        return False

def verify_x_handle(handle: str) -> bool:
    bearer = os.getenv("X_BEARER_TOKEN")
    account = os.getenv("X_ACCOUNT_ID")
    if not bearer or not account:
        return False
    headers = {"Authorization": f"Bearer {bearer}"}
    resp = httpx.get(
        f"https://api.twitter.com/2/users/by/username/{handle}", headers=headers
    )
    if resp.status_code != 200:
        return False
    user_id = resp.json()["data"]["id"]
    resp = httpx.get(
        f"https://api.twitter.com/2/users/{user_id}/following",
        headers=headers,
    )
    if resp.status_code != 200:
        return False
    return any(f.get("id") == account for f in resp.json().get("data", []))


def verify_discord(user_id: str) -> bool:
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild = os.getenv("DISCORD_GUILD_ID")
    if not token or not guild:
        return False
    headers = {"Authorization": f"Bot {token}"}
    resp = httpx.get(
        f"https://discord.com/api/guilds/{guild}/members/{user_id}", headers=headers
    )
    return resp.status_code == 200


def verify_wallet(db: Session, user_id: int, wallet_type: str) -> bool:
    return crud.wallet_registered(db, user_id, wallet_type)


def verify_newsletter(db: Session, email: str) -> bool:
    return crud.newsletter_subscribed(db, email)


def verify_reddit(username: str) -> bool:
    token = os.getenv("REDDIT_TOKEN")
    subreddit = os.getenv("REDDIT_SUBREDDIT")
    if not token or not subreddit:
        return False
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "bounty-app/0.1"}
    resp = httpx.get(
        f"https://oauth.reddit.com/user/{username}/about", headers=headers
    )
    return resp.status_code == 200


def verify_tweet(handle: str) -> bool:
    bearer = os.getenv("X_BEARER_TOKEN")
    hashtag = os.getenv("X_HASHTAG")
    if not bearer or not hashtag:
        return False
    headers = {"Authorization": f"Bearer {bearer}"}
    url = (
        f"https://api.twitter.com/2/tweets/search/recent?query=from:{handle}%20%23{hashtag}"
    )
    resp = httpx.get(url, headers=headers)
    return resp.status_code == 200 and bool(resp.json().get("data"))

