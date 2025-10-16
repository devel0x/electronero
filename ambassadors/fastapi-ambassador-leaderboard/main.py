from __future__ import annotations

import re
import ipaddress
import mimetypes
import base64
import os, json, shutil, shlex, subprocess
import secrets
import hashlib
import subprocess
import csv
import io
import string
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote_plus
import requests
import pandas as pd
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis
from redis.exceptions import LockError


# Load environment variables
load_dotenv()

EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
SHEET_CSV_URL: str | None = os.getenv("SHEET_CSV_URL")
CSV_PATH: str = os.getenv("CSV_PATH", "data/leaderboard.csv")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "30"))
AMBASSADOR_POOL_ADDRESS: str | None = os.getenv("AMBASSADOR_POOL_ADDRESS")
EXPLORER_API = "https://explorer.interchained.org/api/address"
POOL_CACHE_KEY = "ambassador:pool_balance_cache"
POOL_CACHE_TTL = 120  # cache for 2 minutes

TINIFY_API_KEY = "VprDVvZQhDl8g064XrxrrxpGqTg9y4Nh"
TINIFY_ENDPOINT = "https://api.tinify.com/shrink"

KYC_STATUS_PENDING = "pending"
KYC_STATUS_VERIFIED = "verified"
KYC_STATUS_REJECTED = "rejected"
KYC_STATUS_NONE = "not_submitted"
KYC_STATUS_LABELS = {
    KYC_STATUS_PENDING: "Pending Review",
    KYC_STATUS_VERIFIED: "Verified",
    KYC_STATUS_REJECTED: "Rejected",
    KYC_STATUS_NONE: "Not Submitted",
}
KYC_STATUS_BADGE_CLASSES = {
    KYC_STATUS_PENDING: "bg-warning text-dark",
    KYC_STATUS_VERIFIED: "bg-success",
    KYC_STATUS_REJECTED: "bg-danger",
    KYC_STATUS_NONE: "bg-secondary",
}
KYC_STATUS_ORDER = {
    KYC_STATUS_PENDING: 0,
    KYC_STATUS_REJECTED: 1,
    KYC_STATUS_VERIFIED: 2,
    KYC_STATUS_NONE: 3,
}
KYC_DOCUMENT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB safety limit
KYC_TEMP_UPLOAD_ENDPOINT = "https://temp.sh/upload"
KYC_DELETE_AFTER_SECONDS = 7 * 24 * 3600  # 7 days

# Task definitions for the checklist panel
TASK_LIST = [
    ("community_building", "\U0001F539 Community Building – Invite new members, welcome them, keep chats active."),
    ("content_engagement", "\U0001F539 Content Engagement – Post, RT, comment, and boost Interchained/Elara content."),
    ("graphics_media", "\U0001F539 Graphics & Media – Memes, banners, infographics, reels, videos, GIFs."),
    ("copywriting", "\U0001F539 Copywriting – Threads, blogs, captions that explain ITC/Elara."),
    ("education", "\U0001F539 Education – Mini explainers, tutorials, how-to guides."),
    ("spaces_amas", "\U0001F539 Spaces & AMAs – Organize or co-host community calls and events."),
    ("moderation_support", "\U0001F539 Moderation & Support – Help in TG/Discord, answer questions, guide newcomers."),
    ("regional_growth", "\U0001F539 Regional Growth – Promote in your language/region, start local groups."),
    ("creative_campaigns", "\U0001F539 Creative Campaigns – Launch challenges, hashtags, or contests."),
    ("advisory_outreach", "\U0001F539 Advisory & Partnership Outreach – Introduce new partners, projects, or influencers. Advise on negotiations and decisions."),
]

TASK_LABELS = {tid: desc for tid, desc in TASK_LIST}

ADMIN_PASSWORD: str | None = os.getenv("ADMIN_PASSWORD")

INTERCHAINED_CLI = os.getenv("INTERCHAINED_CLI", "interchained-cli")
CLI_EXTRA = os.getenv("CLI_EXTRA", "")
RPC_WALLET = os.getenv("RPC_WALLET")
CLI_TIMEOUT = float(os.getenv("CLI_TIMEOUT", "6.0"))
RANK_MODE = os.getenv("RANK_MODE", "competition").lower()
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REGISTRATIONS_CSV: str = os.getenv("REGISTRATIONS_CSV", "data/registrations.csv")
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
RECOVERY_TTL_SECONDS: int = int(os.getenv("RECOVERY_TTL_SECONDS", "86400"))
MAX_STAKE = 10000.0

EXPECTED_COLUMNS = [
    "name",
    "telegram",
    # "x_handle",
    "points",
    # "posts",
    # "engagements",
    # "referrals",
    "tier",
]

redis_client: Redis = Redis.from_url(REDIS_URL, decode_responses=True)
CACHE_KEY = "leaderboard_cache"
RNG = random.SystemRandom()

ANALYTICS_VISITOR_KEY = "analytics:visits"
ANALYTICS_VISITOR_LIMIT = 500
ANALYTICS_GEO_CACHE_PREFIX = "analytics:geo:"
ANALYTICS_UNIQUE_IPS_KEY = "analytics:unique_ips"
ANALYTICS_TOTAL_VISITS_KEY = "analytics:total_visits"
ANALYTICS_IGNORE_PREFIXES = ("/static", "/favicon.ico", "/health")
GEO_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # one week
MAINTENANCE_FLAG_KEY = "app:maintenance_mode"

# Remove/normalize invalid surrogate code points from Python strings.
_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')

def _safe_text(x: Any) -> str:
    s = str(x)
    if not _SURROGATE_RE.search(s):
        return s
    s = _SURROGATE_RE.sub("�", s)  # replacement char
    return s.encode("utf-8", "replace").decode("utf-8")

def _sanitize_obj(o: Any):
    if isinstance(o, str):
        return _safe_text(o)
    if isinstance(o, dict):
        return {k: _sanitize_obj(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_sanitize_obj(v) for v in o]
    return o

def _load_registrations() -> set[str]:
    try:
        df = pd.read_csv(REGISTRATIONS_CSV)
        df.columns = [c.strip().lower() for c in df.columns]
        if "ambassadors" in df.columns:
            return set(str(e).strip().lower() for e in df["ambassadors"].dropna())
    except Exception:
        return set()
    return set()


REGISTERED_EMAILS = _load_registrations()

REFERRAL_CODE_KEY_PREFIX = "referral:code:"
REFERRALS_HASH_PREFIX = "referrals:"
REFERRAL_CODE_LENGTH = 8
PENDING_VERIFICATION_MIGRATION_KEY = "referrals:migration:pending_all_v2"
MIGRATIONS_DIR = Path(os.getenv("MIGRATIONS_DIR", "data/migrations")).resolve()
PENDING_VERIFICATION_MIGRATION_SENTINEL = (
    MIGRATIONS_DIR / "pending_all_v2.complete"
)

# Legacy in-memory cache kept for reference. Redis is the primary cache, but
# retain the structure for forward compatibility when new metrics are added.
cache: Dict[str, Any] = {
    "columns": [],
    "rows": [],
    "cached_at": None,
    "source": "",
    "pool_balance": 0.0,
    "total_points": 0.0,
    "igp_to_itc": 0.0,
    "itc_to_igp": 0.0,
}


def _normalize_kyc_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in KYC_STATUS_ORDER:
        return raw
    return KYC_STATUS_NONE


def _bool_flag(value: Any) -> str:
    return "yes" if str(value or "").strip().lower() in {"1", "true", "yes", "on"} else "no"


def _parse_birthdate(value: str) -> tuple[bool, str]:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False, "Birthdate is required"
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            dt = datetime.strptime(cleaned, "%Y-%m-%d")
        except ValueError:
            return False, "Birthdate must be in YYYY-MM-DD format"
    if dt.date() > datetime.utcnow().date():
        return False, "Birthdate cannot be in the future"
    return True, dt.date().isoformat()


async def _upload_temp_document(file: UploadFile | None) -> tuple[bool, str, str]:
    if not file or not getattr(file, "filename", ""):
        return True, "", ""

    # ✅ 1. Read file content
    try:
        content = await file.read()
    except Exception as exc:
        return False, "", f"Unable to read uploaded document: {exc}"

    if not content:
        return False, "", "Uploaded document was empty"
    if len(content) > KYC_DOCUMENT_MAX_BYTES:
        return False, "", "Document is too large. Maximum size is 5 MB."

    # ✅ 2. Enforce PNG only
    mime_type, _ = mimetypes.guess_type(file.filename)
    if mime_type != "image/png":
        return False, "", "Only PNG files are allowed."

    # ✅ 3. Compress image with TinyPNG
    try:
        async with httpx.AsyncClient(timeout=60.0, auth=("api", TINIFY_API_KEY)) as client:
            compress_resp = await client.post(
                TINIFY_ENDPOINT,
                content=content
            )

        if compress_resp.status_code != 201:
            return False, "", f"Compression failed: {compress_resp.text}"

        compressed_url = compress_resp.headers.get("Location")
        if not compressed_url:
            return False, "", "Compression API did not return a location URL."

        # ✅ 4. Download compressed image
        async with httpx.AsyncClient(timeout=60.0, auth=("api", TINIFY_API_KEY)) as client:
            download_resp = await client.get(compressed_url)

        if download_resp.status_code != 200:
            return False, "", f"Failed to download compressed image: {download_resp.text}"

        compressed_content = download_resp.content

    except Exception as exc:
        return False, "", f"Image compression failed: {exc}"

    # ✅ 5. Upload compressed PNG to temp storage
    headers = {"X-Delete-After": str(KYC_DELETE_AFTER_SECONDS)}
    payload = {
        "file": (
            file.filename,
            compressed_content,
            "image/png",
        )
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                KYC_TEMP_UPLOAD_ENDPOINT, files=payload, headers=headers
            )
    except Exception as exc:
        return False, "", f"Upload failed: {exc}"

    if response.status_code != 200:
        return False, "", f"Upload failed ({response.status_code})"

    url = response.text.strip()
    if not url.startswith("http"):
        return False, "", "Unexpected response from upload service"

    return True, url, ""
    

async def _set_user_kyc_status(email: str, status: str) -> None:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return
    normalized = _normalize_kyc_status(status)
    await redis_client.hset(
        f"user:{email_norm}",
        mapping={
            "kyc_status": normalized,
        },
    )


async def _get_kyc_record(email: str) -> dict[str, Any]:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return {"status": KYC_STATUS_NONE}
    key = f"kyc:{email_norm}"
    data = await redis_client.hgetall(key)
    if not data:
        return {"status": KYC_STATUS_NONE}
    data["status"] = _normalize_kyc_status(data.get("status"))
    return data


async def _build_profile_account_context(
    request: Request, email: str
) -> dict[str, Any]:
    """Collect shared context for profile, wallet, and KYC pages."""

    user_profile = await redis_client.hgetall(f"user:{email}")
    wallet_value = str(user_profile.get("wallet", ""))

    client_ip = _extract_client_ip(request)
    client_geo = await _resolve_ip_location(client_ip)

    kyc_record = await _get_kyc_record(email)
    kyc_status = _normalize_kyc_status(kyc_record.get("status"))
    await _set_user_kyc_status(email, kyc_status)

    kyc_display = {**kyc_record}
    kyc_display["status"] = kyc_status
    kyc_display["submitted_at_display"] = _format_timestamp(
        kyc_record.get("submitted_at", "")
    )
    kyc_display["updated_at_display"] = _format_timestamp(
        kyc_record.get("updated_at", "")
    )
    kyc_display["reviewed_at_display"] = _format_timestamp(
        kyc_record.get("reviewed_at", "")
    )
    kyc_display["document_uploaded_at_display"] = _format_timestamp(
        kyc_record.get("document_uploaded_at", "")
    )

    show_kyc_toast = kyc_status != KYC_STATUS_VERIFIED

    return {
        "user_profile": user_profile,
        "wallet": wallet_value,
        "client_ip": client_ip,
        "client_location": client_geo.get("label", "Unknown"),
        "kyc": kyc_display,
        "kyc_status": kyc_status,
        "kyc_status_label": KYC_STATUS_LABELS.get(
            kyc_status, "Not Submitted"
        ),
        "kyc_badge_class": KYC_STATUS_BADGE_CLASSES.get(
            kyc_status, "bg-secondary"
        ),
        "show_kyc_toast": show_kyc_toast,
        "today_iso": datetime.utcnow().date().isoformat(),
    }

ACTIVITY_ZSET_PREFIX = "activity:posts:"
ACTIVITY_RESET_KEY = "activity:last_reset"
SCOREPAD_BOOST_POINTS = 1000.0
TRANSFER_HISTORY_LIMIT = int(os.getenv("TRANSFER_HISTORY_LIMIT", "100"))
GLOBAL_TRANSFER_HISTORY_LIMIT = int(os.getenv("GLOBAL_TRANSFER_HISTORY_LIMIT", "500"))
VERIFIED_SEARCH_LIMIT = int(os.getenv("VERIFIED_SEARCH_LIMIT", "50"))
TRANSFER_GLOBAL_LOG_KEY = "transfers:global"
GUARDIAN_SET_KEY = "guardians:emails"
GUARDIAN_USER_FIELD = "guardian"
STAKE_ACTIVE_SET_KEY = "stakes:active"
STAKE_RESERVE_HASH = "stakes:reserve"
STAKE_DURATION_DAYS = int(os.getenv("STAKE_DURATION_DAYS", "7"))
P2P_PRIZE_INDEX_KEY = "p2p:prizes:index"
P2P_PRIZE_HASH_PREFIX = "p2p:prize:"
P2P_PRIZE_SEQ_KEY = "p2p:prize:seq"
P2P_HISTORY_KEY = "p2p:history"
P2P_HISTORY_LIMIT = int(os.getenv("P2P_HISTORY_LIMIT", "300"))
P2P_USER_HISTORY_PREFIX = "p2p:history:user:"
P2P_USER_HISTORY_LIMIT = int(os.getenv("P2P_USER_HISTORY_LIMIT", "100"))

WHEEL_CONFIG_KEY = "gamefi:wheel:config"
WHEEL_HISTORY_KEY = "gamefi:wheel:history"
WHEEL_HISTORY_LIMIT = int(os.getenv("WHEEL_HISTORY_LIMIT", "200"))
WHEEL_LOCK_KEY = "gamefi:wheel:lock"
WHEEL_USER_LOCK_PREFIX = "gamefi:wheel:user:"
WHEEL_LAST_SPIN_PREFIX = "gamefi:wheel:last_spin:"
WHEEL_SEGMENT_FIELD_RE = re.compile(
    r"segment_(\d+)_(id|label|type|tone|weight|multiplier|amount|index)"
)
DEFAULT_WHEEL_ENTRY_FEE = float(os.getenv("WHEEL_DEFAULT_ENTRY_FEE", "50"))
DEFAULT_WHEEL_POOL = float(os.getenv("WHEEL_DEFAULT_POOL", "12500"))
DEFAULT_WHEEL_COOLDOWN_SECONDS = int(os.getenv("WHEEL_DEFAULT_COOLDOWN", "8"))

DEFAULT_WHEEL_SEGMENTS = (
    {
        "id": "multiplier_2x",
        "label": "+2x IGP",
        "type": "multiplier",
        "multiplier": 2,
        "tone": "win",
        "weight": 2,
    },
    {
        "id": "fixed_500",
        "label": "+500 IGP",
        "type": "fixed",
        "amount": 500,
        "tone": "win",
        "weight": 1.5,
    },
    {
        "id": "retry",
        "label": "Try Again",
        "type": "retry",
        "tone": "neutral",
        "weight": 1.2,
    },
    {
        "id": "fixed_1000",
        "label": "+1000 IGP",
        "type": "fixed",
        "amount": 1000,
        "tone": "win",
        "weight": 1,
    },
    {
        "id": "lose",
        "label": "Lose Spin",
        "type": "lose",
        "tone": "lose",
        "weight": 1.4,
    },
    {
        "id": "fixed_250",
        "label": "+250 IGP",
        "type": "fixed",
        "amount": 250,
        "tone": "win",
        "weight": 1.6,
    },
    {
        "id": "multiplier_3x",
        "label": "+3x IGP",
        "type": "multiplier",
        "multiplier": 3,
        "tone": "win",
        "weight": 0.75,
    },
    {
        "id": "bonus",
        "label": "Bonus Spin",
        "type": "bonus",
        "tone": "neutral",
        "weight": 1.25,
    },
)


def _monday_start(dt: datetime | None = None) -> datetime:
    dt = dt or datetime.utcnow()
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def _guardian_emails() -> set[str]:
    members = await redis_client.smembers(GUARDIAN_SET_KEY)
    guardians: set[str] = set()
    for member in members:
        if not member:
            continue
        guardians.add(str(member).strip().lower())
    return guardians


async def _set_guardian_status(email: str, enabled: bool) -> None:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return
    if enabled:
        await redis_client.sadd(GUARDIAN_SET_KEY, email_norm)
        await redis_client.hset(f"user:{email_norm}", GUARDIAN_USER_FIELD, "1")
    else:
        await redis_client.srem(GUARDIAN_SET_KEY, email_norm)
        await redis_client.hdel(f"user:{email_norm}", GUARDIAN_USER_FIELD)


async def _scorepad_balance(email: str) -> float:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return 0.0
    raw = await redis_client.hget("score_pad", email_norm)
    try:
        return float(raw or 0.0)
    except Exception:
        return 0.0


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _default_wheel_segments() -> list[dict[str, Any]]:
    return [dict(segment) for segment in DEFAULT_WHEEL_SEGMENTS]


def _mask_email(email: str) -> str:
    email_norm = _normalize_email(email)
    if not email_norm:
        return "anon"
    local, _, domain = email_norm.partition("@")
    if len(local) <= 2:
        masked_local = f"{local[:1]}***"
    else:
        masked_local = f"{local[:2]}***{local[-1]}"
    domain_hint = domain.split(".")[0] if domain else "mail"
    return f"{masked_local}@{domain_hint}"


def _format_clock(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    return dt.strftime("%H:%M:%S")


def _coerce_wheel_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw)
    try:
        entry_fee = float(config.get("entry_fee", DEFAULT_WHEEL_ENTRY_FEE) or 0.0)
    except Exception:
        entry_fee = DEFAULT_WHEEL_ENTRY_FEE
    try:
        pool_balance = float(config.get("pool_balance", DEFAULT_WHEEL_POOL) or 0.0)
    except Exception:
        pool_balance = DEFAULT_WHEEL_POOL
    try:
        cooldown = int(config.get("cooldown_seconds", DEFAULT_WHEEL_COOLDOWN_SECONDS) or 0)
    except Exception:
        cooldown = DEFAULT_WHEEL_COOLDOWN_SECONDS
    enabled_flag = str(config.get("enabled", "1") or "1").strip()
    status_message = _safe_text(config.get("status_message", "")).strip()
    status_tone_raw = str(config.get("status_tone", "neutral") or "neutral").strip().lower()
    status_tone = status_tone_raw if status_tone_raw in {"neutral", "win", "lose", "bonus"} else "neutral"
    segments_raw = config.get("segments")
    if isinstance(segments_raw, str):
        try:
            segments = json.loads(segments_raw)
        except json.JSONDecodeError:
            segments = _default_wheel_segments()
    elif isinstance(segments_raw, list):
        segments = [dict(s) for s in segments_raw]
    else:
        segments = _default_wheel_segments()
    if not segments:
        segments = _default_wheel_segments()

    normalized_segments: list[dict[str, Any]] = []
    for idx, segment in enumerate(segments):
        seg_type_raw = str(segment.get("type") or "fixed").strip().lower()
        seg_type = (
            seg_type_raw
            if seg_type_raw in {"fixed", "multiplier", "bonus", "retry", "lose"}
            else "fixed"
        )
        seg_tone_raw = str(segment.get("tone") or "neutral").strip().lower()
        seg_tone = (
            seg_tone_raw if seg_tone_raw in {"neutral", "win", "lose", "bonus"} else "neutral"
        )
        seg = {
            "id": segment.get("id") or f"segment_{idx}",
            "label": segment.get("label") or "Spin",
            "type": seg_type,
            "tone": seg_tone,
            "weight": float(segment.get("weight", 1.0) or 1.0),
        }
        if "multiplier" in segment:
            try:
                seg["multiplier"] = float(segment.get("multiplier") or 0.0)
            except Exception:
                seg["multiplier"] = 0.0
        if "amount" in segment:
            try:
                seg["amount"] = float(segment.get("amount") or 0.0)
            except Exception:
                seg["amount"] = 0.0
        try:
            seg_index = int(segment.get("index", idx) or idx)
        except Exception:
            seg_index = idx
        seg["index"] = max(0, seg_index)
        normalized_segments.append(seg)

    return {
        "entry_fee": max(0.0, entry_fee),
        "pool_balance": max(0.0, pool_balance),
        "cooldown_seconds": max(0, cooldown),
        "enabled": enabled_flag not in {"0", "false", "off"},
        "segments": normalized_segments,
        "status_message": status_message,
        "status_tone": status_tone,
    }


async def _ensure_wheel_config() -> dict[str, Any]:
    raw = await redis_client.hgetall(WHEEL_CONFIG_KEY)
    if raw:
        return _coerce_wheel_config(raw)
    now_iso = datetime.utcnow().isoformat()
    config = {
        "entry_fee": DEFAULT_WHEEL_ENTRY_FEE,
        "pool_balance": DEFAULT_WHEEL_POOL,
        "cooldown_seconds": DEFAULT_WHEEL_COOLDOWN_SECONDS,
        "enabled": 1,
        "segments": json.dumps(_default_wheel_segments()),
        "status_message": "Ready to spin. Good luck!",
        "status_tone": "neutral",
        "updated_at": now_iso,
    }
    await redis_client.hset(WHEEL_CONFIG_KEY, mapping=config)
    return _coerce_wheel_config(config)


async def _wheel_history(limit: int = 10) -> list[dict[str, Any]]:
    entries = await redis_client.lrange(WHEEL_HISTORY_KEY, 0, max(limit, 0) - 1)
    history: list[dict[str, Any]] = []
    for raw in entries:
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        created_at = str(payload.get("created_at", ""))
        history.append(
            {
                "player": payload.get("player", "anon"),
                "message": payload.get("message", ""),
                "tone": payload.get("tone", "neutral"),
                "payout": float(payload.get("payout", 0.0) or 0.0),
                "entry_fee": float(payload.get("entry_fee", 0.0) or 0.0),
                "timestamp": created_at,
                "timestamp_display": _format_clock(created_at),
                "segment_id": payload.get("segment_id", ""),
                "segment_label": payload.get("segment_label", ""),
            }
        )
    return history


async def _wheel_state(email: str | None, limit: int = 6) -> dict[str, Any]:
    config = await _ensure_wheel_config()
    scorepad = await _scorepad_balance(email or "") if email else 0.0
    history = await _wheel_history(limit)
    config_message = config.get("status_message") or ""
    status_message = config_message or "Ready to spin. Good luck!"
    status_tone = config.get("status_tone") or "neutral"
    if not config_message and history:
        status_message = history[0]["message"] or status_message
        status_tone = history[0]["tone"] or status_tone
    raw_segments = list(config["segments"])
    raw_segments.sort(key=lambda seg: seg.get("index", 0))
    segments = []
    for idx, segment in enumerate(raw_segments):
        seg = dict(segment)
        seg["index"] = segment.get("index", idx)
        segments.append(seg)
    return {
        "entry_fee": config["entry_fee"],
        "pool_balance": config["pool_balance"],
        "scorepad_balance": scorepad,
        "cooldown_seconds": config["cooldown_seconds"],
        "enabled": config["enabled"],
        "segments": segments,
        "history": history,
        "status_message": status_message,
        "status_tone": status_tone,
        "admin_status_message": config_message,
        "admin_status_tone": config.get("status_tone", "neutral"),
    }


async def _record_wheel_spin(entry: dict[str, Any]) -> None:
    payload = json.dumps(entry)
    await redis_client.lpush(WHEEL_HISTORY_KEY, payload)
    await redis_client.ltrim(WHEEL_HISTORY_KEY, 0, WHEEL_HISTORY_LIMIT - 1)


def _choose_wheel_segment(segments: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    if not segments:
        raise ValueError("no wheel segments configured")
    weights = [max(float(seg.get("weight", 1.0) or 0.0), 0.0) for seg in segments]
    total_weight = sum(weights)
    if total_weight <= 0:
        total_weight = float(len(segments))
        weights = [1.0 for _ in segments]
    roll = RNG.random() * total_weight
    cumulative = 0.0
    for idx, segment in enumerate(segments):
        cumulative += weights[idx]
        if roll <= cumulative or idx == len(segments) - 1:
            return idx, segment
    return len(segments) - 1, segments[-1]


def _wheel_outcome(
    segment: dict[str, Any],
    entry_fee: float,
    pool_after_fee: float,
) -> tuple[float, str, str, dict[str, float]]:
    seg_type = str(segment.get("type", "")).strip().lower()
    label = segment.get("label") or "Spin"
    tone = segment.get("tone", "neutral")
    pool_available = max(0.0, pool_after_fee)
    payout = 0.0
    message = label
    detail: dict[str, float] = {}

    if seg_type == "multiplier":
        try:
            multiplier = float(segment.get("multiplier", 0.0) or 0.0)
        except Exception:
            multiplier = 0.0
        potential = max(0.0, entry_fee * multiplier)
        payout = min(pool_available, potential)
        detail["potential"] = potential
        detail["multiplier"] = multiplier
        if payout <= 0:
            tone = "neutral"
            message = "The pool is empty. Admins need to reload rewards."
        elif payout + 1e-6 < potential:
            tone = "neutral"
            message = f"Pool light! Paid out {payout:.0f} IGP of {potential:.0f}."
        else:
            tone = "win"
            message = f"Multiplier hit! +{payout:.0f} IGP."
    elif seg_type == "fixed":
        try:
            amount = float(segment.get("amount", 0.0) or 0.0)
        except Exception:
            amount = 0.0
        potential = max(0.0, amount)
        payout = min(pool_available, potential)
        detail["potential"] = potential
        if payout <= 0:
            tone = "neutral"
            message = "The pool is empty. Admins need to reload rewards."
        elif payout + 1e-6 < potential:
            tone = "neutral"
            message = f"Partial win: paid {payout:.0f} IGP from the remaining pool."
        else:
            tone = "win"
            message = f"Jackpot drop! +{payout:.0f} IGP."
    elif seg_type == "bonus":
        refund = min(pool_available, max(0.0, entry_fee))
        payout = refund
        detail["refund"] = refund
        if refund <= 0:
            tone = "neutral"
            message = "Bonus unlocked, but the pool is empty. No refund issued."
        elif refund + 1e-6 < entry_fee:
            tone = "neutral"
            message = "Bonus spin unlocked! Partial refund applied while the pool refills."
        else:
            tone = "neutral"
            message = "Bonus spin! Entry refunded — keep the wheel moving."
    elif seg_type == "retry":
        refund = min(pool_available, max(0.0, entry_fee))
        payout = refund
        detail["refund"] = refund
        if refund <= 0:
            tone = "neutral"
            message = "Try again streak triggered, but the pool is empty. Entry stays staked."
        elif refund + 1e-6 < entry_fee:
            tone = "neutral"
            message = "Try again streak triggered with a partial refund while the pool reloads."
        else:
            tone = "neutral"
            message = "Try again! Entry fee refunded for another spin."
    else:
        payout = 0.0
        tone = "lose"
        message = "House wins — bank the lesson and spin again when ready."

    return payout, message, tone, detail


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _format_dt(value: datetime | None, pattern: str = "%b %d, %Y") -> str:
    if not value:
        return ""
    return value.strftime(pattern)


def _format_duration(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "Completed"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append("<1m")
    return " ".join(parts)


def _stake_key(email_norm: str) -> str:
    return f"stake:{email_norm}"


async def _cleanup_stake_reserve(email_norm: str) -> None:
    raw = await redis_client.hget(STAKE_RESERVE_HASH, email_norm)
    try:
        value = float(raw or 0.0)
    except Exception:
        value = 0.0
    if value <= 1e-9:
        await redis_client.hdel(STAKE_RESERVE_HASH, email_norm)


async def _staked_amount(email: str) -> float:
    email_norm = _normalize_email(email)
    if not email_norm:
        return 0.0
    raw = await redis_client.hget(STAKE_RESERVE_HASH, email_norm)
    try:
        value = float(raw or 0.0)
    except Exception:
        value = 0.0
    return value if value > 0 else 0.0


async def _get_stake(email: str) -> dict[str, Any] | None:
    email_norm = _normalize_email(email)
    if not email_norm:
        return None
    data = await redis_client.hgetall(_stake_key(email_norm))
    if not data:
        return None
    try:
        amount = float(data.get("amount", 0) or 0)
    except Exception:
        amount = 0.0
    if amount <= 0:
        return None
    started_at = _parse_iso(data.get("started_at"))
    week_start = _parse_iso(data.get("week_start"))
    week_end = _parse_iso(data.get("week_end"))
    payout_week_start = _parse_iso(data.get("payout_week_start"))
    payout_week_end = _parse_iso(data.get("payout_week_end"))
    ends_at = _parse_iso(data.get("ends_at"))
    if not ends_at and week_end:
        ends_at = week_end
    elif not ends_at and started_at:
        ends_at = started_at + timedelta(days=STAKE_DURATION_DAYS)
    return {
        "email": email_norm,
        "amount": amount,
        "status": data.get("status", "active"),
        "created_by": data.get("created_by", "user"),
        "started_at": started_at,
        "week_start": week_start,
        "week_end": week_end,
        "payout_week_start": payout_week_start,
        "payout_week_end": payout_week_end,
        "ends_at": ends_at,
        "snapshots": {
            "display_name": data.get("display_name"),
            "telegram": data.get("telegram_snapshot") or data.get("telegram"),
        },
    }


def _stake_view(stake: dict[str, Any]) -> dict[str, Any]:
    view = dict(stake)
    ends_at = stake.get("ends_at")
    if not ends_at and stake.get("week_end"):
        ends_at = stake.get("week_end")
    view["ends_at"] = ends_at
    delta = (ends_at - datetime.utcnow()) if ends_at else timedelta()
    view["time_remaining_label"] = _format_duration(delta)
    view["is_mature"] = delta.total_seconds() <= 0
    view["started_at_display"] = _format_dt(stake.get("started_at"), "%b %d, %Y %H:%M UTC")
    view["week_start_display"] = _format_dt(stake.get("week_start"))
    view["week_end_display"] = _format_dt(stake.get("week_end"))
    view["payout_start_display"] = _format_dt(stake.get("payout_week_start"))
    view["payout_end_display"] = _format_dt(stake.get("payout_week_end"))
    view["ends_at_display"] = _format_dt(ends_at)
    try:
        view["amount_display"] = f"{float(stake.get('amount', 0.0) or 0.0):.2f}"
    except Exception:
        view["amount_display"] = f"{stake.get('amount', 0.0)}"
    if view["payout_start_display"] and view["payout_end_display"]:
        view["payout_window_display"] = f"{view['payout_start_display']} – {view['payout_end_display']}"
    else:
        view["payout_window_display"] = view.get("payout_start_display", "")
    return view


async def _stake_balances(email: str, profile: dict[str, Any] | None = None) -> dict[str, float]:
    email_norm = _normalize_email(email)
    if not email_norm:
        return {"total": 0.0, "available": 0.0, "staked": 0.0, "scorepad": 0.0}
    profile_data = profile
    if profile_data is None:
        profile_data = await _ambassador_entry_by_email(email_norm)
    pad_balance = await _scorepad_balance(email_norm)
    total_points = 0.0
    if profile_data and profile_data.get("guardian"):
        total_points = max(pad_balance, 0.0)
    elif profile_data:
        try:
            total_points = float(profile_data.get("points", 0.0) or 0.0)
        except Exception:
            total_points = 0.0
    else:
        total_points = max(pad_balance, 0.0)
    staked = await _staked_amount(email_norm)
    available = max(total_points - staked, 0.0)
    return {
        "total": total_points,
        "available": total_points,
        "staked": staked,
        "scorepad": pad_balance,
    }


async def _create_stake(email: str, amount: float, created_by: str = "user") -> tuple[bool, str | None]:
    email_norm = _normalize_email(email)
    if not email_norm:
        return False, "Invalid email provided."
    if amount <= 0:
        return False, "Stake amount must be positive."

    # ✅ Try to acquire a short-lived lock (prevents double-click / double-submit)
    lock_key = f"stake:lock:{email_norm}"
    lock_acquired = await redis_client.set(lock_key, "1", nx=True, ex=15)  # expires after 15s
    if not lock_acquired:
        return False, "A staking operation is already in progress. Please wait a moment."

    try:
        # ✅ Check if already staked
        existing = await _get_stake(email_norm)
        if existing:
            return False, "An active stake already exists."

        # ✅ Get balances and raw score_pad before staking
        balances = await _stake_balances(email_norm)
        total_points = balances.get("total", 0.0)
        current_scorepad = await _scorepad_balance(email_norm)

        # ✅ Hard guard: never allow staking more than total points
        if amount > total_points + 1e-9:
            return False, f"Stake amount exceeds your total balance ({total_points:.2f} IGP)."

        # ✅ Critical guard: ensure score_pad covers this stake
        if current_scorepad < amount - 1e-9:
            return False, (
                f"Insufficient unlocked balance. You currently have {current_scorepad:.2f} IGP available to stake."
            )

        # ✅ Safety cap
        if amount > MAX_STAKE:
            return False, f"Stake amount exceeds the maximum allowed of {MAX_STAKE} IGP."

        # ---------- stake logic continues ----------
        now = datetime.utcnow()
        week_start = _monday_start(now)
        week_end = week_start + timedelta(days=7)
        ends_at = now + timedelta(days=STAKE_DURATION_DAYS)

        payout_week_start = _monday_start(ends_at + timedelta(days=STAKE_DURATION_DAYS))
        if payout_week_start <= ends_at:
            payout_week_start += timedelta(days=STAKE_DURATION_DAYS)
        payout_week_end = payout_week_start + timedelta(days=STAKE_DURATION_DAYS)

        mapping: dict[str, Any] = {
            "email": email_norm,
            "amount": f"{amount:.8f}",
            "status": "active",
            "created_by": created_by,
            "started_at": now.isoformat(),
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "payout_week_start": payout_week_start.isoformat(),
            "payout_week_end": payout_week_end.isoformat(),
            "ends_at": ends_at.isoformat(),
            "duration_days": str(STAKE_DURATION_DAYS),
        }

        profile_snapshot = await redis_client.hgetall(f"user:{email_norm}")
        if profile_snapshot.get("name"):
            mapping["display_name"] = profile_snapshot["name"]
        if profile_snapshot.get("telegram"):
            mapping["telegram_snapshot"] = profile_snapshot["telegram"]

        pipe = redis_client.pipeline()
        pipe.hset(_stake_key(email_norm), mapping=mapping)
        pipe.sadd(STAKE_ACTIVE_SET_KEY, email_norm)
        if amount:
            pipe.hincrbyfloat("score_pad", email_norm, -amount)
            pipe.hincrbyfloat(STAKE_RESERVE_HASH, email_norm, amount)
        await pipe.execute()

        try:
            await _load_csv()
        except Exception as exc:
            print(f"[staking] failed to refresh leaderboard cache after stake: {exc}")

        return True, None

    finally:
        # ✅ Always release the lock — even if an exception occurs
        await redis_client.delete(lock_key)


async def _release_stake(email: str) -> tuple[bool, str | None]:
    email_norm = _normalize_email(email)
    if not email_norm:
        return False, "Invalid email provided."
    stake = await _get_stake(email_norm)
    if not stake:
        return False, "No active stake found."
    amount = float(stake.get("amount", 0.0) or 0.0)
    pipe = redis_client.pipeline()
    if amount:
        pipe.hincrbyfloat("score_pad", email_norm, amount)
    pipe.delete(_stake_key(email_norm))
    pipe.srem(STAKE_ACTIVE_SET_KEY, email_norm)
    if amount:
        pipe.hincrbyfloat(STAKE_RESERVE_HASH, email_norm, -amount)
    await pipe.execute()
    await _cleanup_stake_reserve(email_norm)
    try:
        await _load_csv()
    except Exception as exc:
        print(f"[staking] failed to refresh leaderboard cache after release: {exc}")
    return True, None


async def _all_active_stakes() -> list[dict[str, Any]]:
    members = await redis_client.smembers(STAKE_ACTIVE_SET_KEY)
    stakes: list[dict[str, Any]] = []
    for email_norm in sorted(members):
        stake = await _get_stake(email_norm)
        if not stake:
            await redis_client.srem(STAKE_ACTIVE_SET_KEY, email_norm)
            continue
        profile = await _ambassador_entry_by_email(email_norm)
        balances = await _stake_balances(email_norm, profile=profile)
        user_profile = await redis_client.hgetall(f"user:{email_norm}")
        telegram_display = (
            user_profile.get("telegram")
            or (stake.get("snapshots") or {}).get("telegram")
            or (profile or {}).get("telegram")
        )
        name_display = (
            user_profile.get("name")
            or (stake.get("snapshots") or {}).get("display_name")
            or (profile or {}).get("name")
        )
        view = _stake_view(stake)
        view.update(
            {
                "email": email_norm,
                "telegram": telegram_display,
                "name": name_display,
                "points": balances["total"],
                "available_points": balances["available"],
            }
        )
        stakes.append(view)
    stakes.sort(
        key=lambda item: item.get("week_start")
        or item.get("started_at")
        or datetime.min
    )
    return stakes


async def _activity_window_bounds(now: datetime | None = None) -> tuple[float, float]:
    now = now or datetime.utcnow()
    week_start = _monday_start(now)
    week_end = week_start + timedelta(days=7)
    reset_raw = await redis_client.get(ACTIVITY_RESET_KEY)
    if reset_raw:
        try:
            reset_dt = datetime.fromisoformat(reset_raw)
            if reset_dt > week_start:
                week_start = reset_dt
        except ValueError:
            pass
    return week_start.timestamp(), week_end.timestamp()


async def _maintenance_guard(request: Request):
    if await _maintenance_enabled():
        # let admins bypass
        if await _current_admin(request):
            return None
        # block ambassadors
        if request.url.path.startswith("/api"):
            return JSONResponse({"ok": False, "error": "maintenance_mode"}, status_code=503)
        return templates.TemplateResponse(
            "maintenance.html",
            {"request": request},
            status_code=503,
        )
    return None

# def _get_pool_balance() -> float:
#     """Fetch ITC balance for the ambassador pool address via interchained-cli."""
#     if not AMBASSADOR_POOL_ADDRESS:
#         return 0.0
#     try:
#         result = subprocess.run(
#             ["interchained-cli", "getbalance", AMBASSADOR_POOL_ADDRESS],
#             capture_output=True,
#             text=True,
#             check=True,
#         )
#         return float(result.stdout.strip())
#     except Exception:
#         return 0.0

def _which_cli() -> str | None:
    # Use absolute path from .env if provided and exists
    if INTERCHAINED_CLI and os.path.isabs(INTERCHAINED_CLI) and os.path.exists(INTERCHAINED_CLI):
        return INTERCHAINED_CLI
    # Otherwise fall back to PATH lookup
    return shutil.which(INTERCHAINED_CLI)

def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    cli = _which_cli()
    if not cli:
        raise RuntimeError(f"interchained-cli not found (INTERCHAINED_CLI={INTERCHAINED_CLI})")
    extra = shlex.split(CLI_EXTRA, posix=False) if CLI_EXTRA else []
    return subprocess.run([cli, *extra, *args],
                          capture_output=True, text=True,
                          check=True, timeout=CLI_TIMEOUT)

def _daemon_ready() -> bool:
    try:
        _run_cli("getblockchaininfo")
        return True
    except Exception as e:
        print(f"[daemon_ready] {e}")
        return False

# def _get_pool_balance() -> float:
#     addr = AMBASSADOR_POOL_ADDRESS
#     if not addr:
#         return 250.0
#     if not _daemon_ready():
#         return 250.0
#     try:
#         cp = _run_cli("scantxoutset", "start", f'["addr({addr})"]')
#         data = json.loads(cp.stdout)
#         if data.get("success"):
#             base_amount = float(data.get("total_amount", 0.0))
#             ops_amount = base_amount * 3000 / 10000
#             operations_reserve = 300
#             true_amount = base_amount - ops_amount - operations_reserve
#             return true_amount
#     except subprocess.CalledProcessError as e:
#         print(f"[pool_balance] scantxoutset failed: {e.stderr.strip()}")
#     except Exception as e:
#         print(f"[pool_balance] scantxoutset error: {e}")
#     if RPC_WALLET:
#         try:
#             cp = _run_cli(f"-rpcwallet={RPC_WALLET}", "getbalance")
#             base_amount = float(cp.stdout.strip())
#             ops_amount = base_amount * 3000 / 10000
#             operations_reserve = 300
#             true_amount = base_amount - ops_amount - operations_reserve
#             return true_amount
#         except Exception as e:
#             print(f"[pool_balance] getbalance (wallet) error: {e}")
#     try:
#         cp = _run_cli("getreceivedbyaddress", addr, "0")
#         base_amount = float(cp.stdout.strip())
#         ops_amount = base_amount * 3000 / 10000
#         operations_reserve = 300
#         true_amount = base_amount - ops_amount - operations_reserve
#         return true_amount
#     except Exception as e:
#         print(f"[pool_balance] getreceivedbyaddress error: {e}")
#     return 250.0

async def _get_pool_balance() -> float:
    addr = AMBASSADOR_POOL_ADDRESS
    if not addr:
        return 500.0

    # ✅ 1. Try Redis cache first
    try:
        cached = await redis_client.get(POOL_BALANCE_CACHE_KEY)
        if cached is not None:
            cached_val = float(cached)
            return cached_val if cached_val >= 500.0 else 500.0
    except Exception as e:
        print(f"[pool_balance] Redis cache read failed: {e}")

    # ✅ 2. Fallback to Explorer API if cache is missing/expired
    try:
        r = requests.get(f"{EXPLORER_API}/{addr}", timeout=45)
        r.raise_for_status()
        data = r.json()

        # Extract balance (satoshis → ITC)
        balance_sat = data.get("txHistory", {}).get("balanceSat", 0)
        base_amount = balance_sat / 1e8

        # Apply operations + reserve deductions
        ops_amount = base_amount * 0.90
        operations_reserve = 6030
        true_amount = base_amount - ops_amount - operations_reserve

        result = max(true_amount / 2, 0.0)

        # ✅ Always enforce a minimum of 500.0
        if result < 500.0:
            result = 500.0

        # ✅ 3. Cache result for 2 minutes
        try:
            await redis_client.setex(POOL_BALANCE_CACHE_KEY, POOL_BALANCE_CACHE_TTL, result)
        except Exception as e:
            print(f"[pool_balance] Redis cache write failed: {e}")

        return result

    except requests.Timeout:
        print("[pool_balance] Explorer API timeout (45s)")
    except requests.RequestException as e:
        print(f"[pool_balance] Explorer API error: {e}")
    except Exception as e:
        print(f"[pool_balance] Unexpected error: {e}")

    # ✅ 4. Final fallback if everything fails
    return 500.0
    

async def _load_csv() -> Dict[str, Any]:
    path = SHEET_CSV_URL or CSV_PATH
    source = "google_sheet" if SHEET_CSV_URL else "local_csv"

    try:
        # Try UTF-8 first
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        # If UTF-8 fails, fallback to latin-1
        df = pd.read_csv(path, encoding="latin-1")
    except Exception as exc:
        raise RuntimeError(f"Failed to read CSV from {path}: {exc}") from exc

    # 🔧 make headers consistent
    df.columns = [str(c).strip().lower() for c in df.columns]

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Apply any admin-provided score padding before ranking.
    pads = await redis_client.hgetall("score_pad")
    norm_map: dict[str, float] = {}
    for k, v in pads.items():
        try:
            norm_map[k.strip().lower()] = float(v)
        except Exception:
            continue

    guardians = await _guardian_emails()

    if "email" in df.columns:
        df["email"] = df["email"].astype(str).str.strip().str.lower()
        df["__email_norm"] = df["email"]  # already normalized
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
        pads = await redis_client.hgetall("score_pad")
        norm_map = {k.strip().lower(): float(v) for k, v in pads.items() if v is not None}
        df["points"] = df["points"] + df["__email_norm"].map(norm_map).fillna(0)
    else:
        df["points"] = pd.to_numeric(df.get("points"), errors="coerce").fillna(0)
        df["__email_norm"] = ""


    if "rank" in df.columns:
        df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
        df = df.sort_values("rank", ascending=True)
    else:
        df = df.sort_values("points", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
    # if "rank" in df.columns:
    #     df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    #     df = df.sort_values("rank", ascending=True)
    # else:
    #     df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
    #     df = df.sort_values("points", ascending=False).reset_index(drop=True)
    #     df.insert(0, "rank", range(1, len(df) + 1))
    # df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
    
    # # ensure numeric points
    # df["points"] = pd.to_numeric(df.get("points"), errors="coerce").fillna(0)

    # # sort by points desc (and optionally tie-break by name/telegram to make display stable)
    # df = df.sort_values(["points", "name"], ascending=[False, True]).reset_index(drop=True)

    # # assign ranks with ties sharing the same rank
    # if RANK_MODE == "dense":
    #     # 1,1,2,3...
    #     df["rank"] = df["points"].rank(method="dense", ascending=False).astype(int)
    # else:
    #     # competition ranking: 1,1,3,4...
    #     df["rank"] = df["points"].rank(method="min", ascending=False).astype(int)

    # ensure numeric points, then sort
    df["points"] = pd.to_numeric(df.get("points"), errors="coerce").fillna(0)
    df = df.sort_values(["points", "name"], ascending=[False, True]).reset_index(drop=True)

    # ---- DENSE RANK: 1,1,2,3... by unique points ----
    # (no gaps no matter how many users share a score)
    guardian_mask = df["__email_norm"].isin(guardians)
    non_guardian_mask = ~guardian_mask
    df["rank"] = ""
    if non_guardian_mask.any():
        uniq = sorted(df.loc[non_guardian_mask, "points"].unique(), reverse=True)
        rank_map = {v: i + 1 for i, v in enumerate(uniq)}
        df.loc[non_guardian_mask, "rank"] = (
            df.loc[non_guardian_mask, "points"].map(rank_map).astype(int)
        )

    pool_balance = round(await _get_pool_balance(), 8)
    total_points = float(df.loc[non_guardian_mask, "points"].sum())
    igp_to_itc = pool_balance / total_points if total_points else 0.0
    itc_to_igp = total_points / pool_balance if pool_balance else 0.0
    df["pending_reward"] = 0.0
    if total_points > 0:
        df.loc[non_guardian_mask, "pending_reward"] = (
            df.loc[non_guardian_mask, "points"] / total_points
        ) * pool_balance
    df["pending_reward"] = df["pending_reward"].astype(float).round(8)

    if "__email_norm" in df.columns:
        df = df.drop(columns="__email_norm")

    base_cols = [
        "rank",
        "name",
        "email",
        "telegram",
        "points",
        "tier",
        "pending_reward",
    ]
    df = df[[c for c in base_cols if c in df.columns]]

    df = df.fillna("").infer_objects(copy=False)
    df["pending_reward"] = df["pending_reward"].apply(lambda x: f"{x:.8f}")

    data = {
        "columns": list(df.columns),
        "rows": df.astype(str).to_dict(orient="records"),
        "cached_at": datetime.utcnow().isoformat(),
        "source": source,
        "pool_balance": pool_balance,
        "total_points": round(total_points, 8),
        "igp_to_itc": round(igp_to_itc, 8),
        "itc_to_igp": round(itc_to_igp, 8),
    }
    await redis_client.set(CACHE_KEY, json.dumps(data), ex=CACHE_TTL_SECONDS)
    return data


def _to_lower_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


async def _leaderboard_entries(force_refresh: bool = False) -> list[dict[str, Any]]:
    data = await _get_cached_data(force_refresh=force_refresh)
    entries: list[dict[str, Any]] = []
    guardians = await _guardian_emails()
    for raw in data.get("rows", []):
        email_raw = str(raw.get("email", "")).strip()
        email_norm = email_raw.lower()
        telegram_raw = str(raw.get("telegram", "")).strip()
        telegram_norm = telegram_raw.lstrip("@").lower()
        try:
            points_val = float(raw.get("points", 0) or 0)
        except Exception:
            try:
                points_val = float(str(raw.get("points", "0")).replace(",", ""))
            except Exception:
                points_val = 0.0
        is_guardian = email_norm in guardians if email_norm else False
        entries.append(
            {
                "email": email_norm,
                "email_display": email_raw,
                "telegram": telegram_raw,
                "telegram_norm": telegram_norm,
                "name": raw.get("name", ""),
                "tier": raw.get("tier", ""),
                "points": points_val,
                "guardian": is_guardian,
            }
        )
    return entries


async def _ambassador_entry_by_email(email: str) -> dict[str, Any] | None:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return None
    entries = await _leaderboard_entries()
    match = next((row for row in entries if row.get("email") == email_norm), None)
    if match:
        return match
    # Fall back to telegram lookup using stored profile data
    user = await redis_client.hgetall(f"user:{email_norm}")
    telegram_norm = str(user.get("telegram", "")).strip().lstrip("@").lower()
    if telegram_norm:
        return next(
            (row for row in entries if row.get("telegram_norm") == telegram_norm),
            None,
        )
    return None


async def _email_from_telegram(telegram_norm: str) -> str | None:
    handle = str(telegram_norm or "").strip().lstrip("@").lower()
    if not handle:
        return None
    async for key in redis_client.scan_iter("user:*"):
        data = await redis_client.hgetall(key)
        tele_norm = str(data.get("telegram", "")).strip().lstrip("@").lower()
        if tele_norm == handle:
            return key.split(":", 1)[1]
    return None


async def _ambassador_entry_by_identifier(identifier: str) -> dict[str, Any] | None:
    ident = str(identifier or "").strip()
    if not ident:
        return None
    ident_norm = ident.lower()
    telegram_norm = ident.lstrip("@").lower()
    entries = await _leaderboard_entries()
    entry = next(
        (
            row
            for row in entries
            if row.get("email") == ident_norm
            or row.get("telegram_norm") == telegram_norm
        ),
        None,
    )
    if entry and not entry.get("email") and telegram_norm:
        email_from_store = await _email_from_telegram(telegram_norm)
        if email_from_store:
            entry = {
                **entry,
                "email": email_from_store,
                "email_display": email_from_store,
            }
    return entry


async def _transfer_history(email: str) -> list[dict[str, Any]]:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return []
    key = f"transfers:{email_norm}"
    entries = await redis_client.lrange(key, 0, TRANSFER_HISTORY_LIMIT - 1)
    history: list[dict[str, Any]] = []
    for raw in entries:
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        history.append(entry)
    return history


async def _all_transfer_history() -> list[dict[str, Any]]:
    entries = await redis_client.lrange(
        TRANSFER_GLOBAL_LOG_KEY, 0, GLOBAL_TRANSFER_HISTORY_LIMIT - 1
    )
    history: list[dict[str, Any]] = []
    for raw in entries:
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        history.append(entry)
    return history


def _p2p_prize_key(prize_id: str) -> str:
    return f"{P2P_PRIZE_HASH_PREFIX}{prize_id}".strip()


def _p2p_parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _p2p_parse_quantity(value: Any) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _p2p_quantity_label(quantity: int | None) -> str:
    if quantity is None:
        return "Unlimited"
    if quantity < 0:
        return "Unlimited"
    return str(quantity)


async def _p2p_prize(prize_id: str) -> dict[str, Any] | None:
    pid = str(prize_id or "").strip()
    if not pid:
        return None
    data = await redis_client.hgetall(_p2p_prize_key(pid))
    if not data:
        return None
    quantity = _p2p_parse_quantity(data.get("quantity"))
    try:
        cost = float(data.get("cost", 0.0) or 0.0)
    except Exception:
        cost = 0.0
    active = _p2p_parse_bool(data.get("active", "1"))
    available = active and (quantity is None or quantity > 0)
    return {
        "id": data.get("id") or pid,
        "name": _safe_text(data.get("name", "")),
        "description": _safe_text(data.get("description", "")),
        "cost": cost,
        "quantity": quantity,
        "active": active,
        "available": available,
        "quantity_label": _p2p_quantity_label(quantity),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "last_redeemed_at": data.get("last_redeemed_at", ""),
        "last_redeemed_by": data.get("last_redeemed_by", ""),
    }


async def _p2p_prizes(include_inactive: bool = False) -> list[dict[str, Any]]:
    ids = await redis_client.zrange(P2P_PRIZE_INDEX_KEY, 0, -1)
    prizes: list[dict[str, Any]] = []
    for pid in ids:
        entry = await _p2p_prize(pid)
        if not entry:
            continue
        if include_inactive or entry.get("active"):
            prizes.append(entry)
    return prizes


async def _p2p_recent_history(limit: int = 50) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    entries = await redis_client.lrange(P2P_HISTORY_KEY, 0, limit - 1)
    history: list[dict[str, Any]] = []
    for raw in entries:
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        history.append(entry)
    return history


async def _p2p_user_history(email: str, limit: int = P2P_USER_HISTORY_LIMIT) -> list[dict[str, Any]]:
    email_norm = _normalize_email(email)
    if not email_norm or limit <= 0:
        return []
    key = f"{P2P_USER_HISTORY_PREFIX}{email_norm}"
    entries = await redis_client.lrange(key, 0, limit - 1)
    history: list[dict[str, Any]] = []
    for raw in entries:
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        history.append(entry)
    return history


async def _record_p2p_redemption(
    email: str,
    prize: dict[str, Any],
    cost: float,
    balance_before: float,
    note: str = "",
) -> None:
    email_norm = _normalize_email(email)
    if not email_norm:
        return
    timestamp = datetime.utcnow().isoformat()
    balance_after = max(balance_before - cost, 0.0)
    note_clean = _safe_text(note)[:500]
    user_profile = await redis_client.hgetall(f"user:{email_norm}")
    telegram = user_profile.get("telegram") or (prize or {}).get("telegram")
    display_name = user_profile.get("name")
    prize_id = (prize or {}).get("id") or ""
    prize_name = (prize or {}).get("name") or prize_id
    user_entry = {
        "timestamp": timestamp,
        "prize_id": prize_id,
        "prize_name": prize_name,
        "cost": cost,
        "note": note_clean,
        "balance_before": balance_before,
        "balance_after": balance_after,
    }
    global_entry = {
        "timestamp": timestamp,
        "email": email_norm,
        "telegram": telegram,
        "name": display_name,
        "prize_id": prize_id,
        "prize_name": prize_name,
        "cost": cost,
        "note": note_clean,
        "balance_before": balance_before,
        "balance_after": balance_after,
    }
    pipe = redis_client.pipeline()
    pipe.lpush(f"{P2P_USER_HISTORY_PREFIX}{email_norm}", json.dumps(user_entry))
    pipe.ltrim(f"{P2P_USER_HISTORY_PREFIX}{email_norm}", 0, P2P_USER_HISTORY_LIMIT - 1)
    pipe.lpush(P2P_HISTORY_KEY, json.dumps(global_entry))
    pipe.ltrim(P2P_HISTORY_KEY, 0, P2P_HISTORY_LIMIT - 1)
    await pipe.execute()


async def _p2p_delete_prize(prize_id: str) -> None:
    pid = str(prize_id or "").strip()
    if not pid:
        return
    pipe = redis_client.pipeline()
    pipe.delete(_p2p_prize_key(pid))
    pipe.zrem(P2P_PRIZE_INDEX_KEY, pid)
    await pipe.execute()


async def _record_transfer(
    source: dict[str, Any],
    destination: dict[str, Any],
    amount: float,
    sender_total_before: float,
    receiver_total_before: float,
) -> None:
    timestamp = datetime.utcnow().isoformat()
    sender_email = source.get("email", "")
    dest_email = destination.get("email", "")
    sender_after = max(sender_total_before - amount, 0.0)
    receiver_after = receiver_total_before + amount

    sent_entry = {
        "direction": "sent",
        "amount": amount,
        "timestamp": timestamp,
        "to": destination.get("email_display") or dest_email,
        "to_telegram": destination.get("telegram"),
        "to_name": destination.get("name", ""),
        "balance_after": sender_after,
    }
    received_entry = {
        "direction": "received",
        "amount": amount,
        "timestamp": timestamp,
        "from": source.get("email_display") or sender_email,
        "from_telegram": source.get("telegram"),
        "from_name": source.get("name", ""),
        "balance_after": receiver_after,
    }
    global_entry = {
        "timestamp": timestamp,
        "amount": amount,
        "source": sender_email,
        "source_telegram": source.get("telegram"),
        "source_name": source.get("name", ""),
        "destination": dest_email,
        "destination_telegram": destination.get("telegram"),
        "destination_name": destination.get("name", ""),
    }

    pipe = redis_client.pipeline()
    if sender_email:
        pipe.lpush(f"transfers:{sender_email}", json.dumps(sent_entry))
        pipe.ltrim(f"transfers:{sender_email}", 0, TRANSFER_HISTORY_LIMIT - 1)
    if dest_email:
        pipe.lpush(f"transfers:{dest_email}", json.dumps(received_entry))
        pipe.ltrim(f"transfers:{dest_email}", 0, TRANSFER_HISTORY_LIMIT - 1)
    pipe.lpush(TRANSFER_GLOBAL_LOG_KEY, json.dumps(global_entry))
    pipe.ltrim(TRANSFER_GLOBAL_LOG_KEY, 0, GLOBAL_TRANSFER_HISTORY_LIMIT - 1)
    if pipe.command_stack:
        await pipe.execute()


async def _zero_transfer_history() -> None:
    """Preserve transfer entries but zero any recorded amounts/balances.

    The real source of truth for points remains the ``score_pad`` hash, so
    zeroing the ledger does *not* undo past transfers or restore balances.
    Admins sometimes want to clear sensitive totals without erasing who
    interacted with whom, so this helper rewrites each transfer list while
    keeping metadata intact and setting the displayed amounts to ``0``.
    """
    async for key in redis_client.scan_iter("transfers:*"):
        entries = await redis_client.lrange(key, 0, -1)
        if not entries:
            continue
        updated: list[str] = []
        for raw in entries:
            try:
                entry = json.loads(raw)
            except Exception:
                updated.append(raw)
                continue
            entry["amount"] = 0.0
            if key != TRANSFER_GLOBAL_LOG_KEY and "balance_after" in entry:
                entry["balance_after"] = 0.0
            updated.append(json.dumps(entry))
        pipe = redis_client.pipeline()
        pipe.delete(key)
        if updated:
            pipe.rpush(key, *updated)
        await pipe.execute()


async def _delete_transfer_history() -> None:
    """Remove all transfer history keys and their stored entries entirely."""
    keys = [key async for key in redis_client.scan_iter("transfers:*")]
    if keys:
        await redis_client.delete(*keys)


async def _get_cached_data(force_refresh: bool = False) -> Dict[str, Any]:
    raw = await redis_client.get(CACHE_KEY)
    if force_refresh or raw is None:
        data = await _load_csv()
    else:
        data = json.loads(raw)
        if any(k not in data for k in ("total_points", "igp_to_itc", "itc_to_igp")):
            data = await _load_csv()
    return data


async def _current_email(request: Request) -> str | None:
    token = request.cookies.get("session")
    if not token:
        return None
    return await redis_client.get(f"session:{token}")


async def _current_admin(request: Request) -> bool:
    token = request.cookies.get("admin")
    if not token:
        return False
    return await redis_client.get(f"admin_session:{token}") == "admin"


async def _maintenance_enabled() -> bool:
    value = await redis_client.get(MAINTENANCE_FLAG_KEY)
    return str(value) == "1"


async def _set_maintenance(enabled: bool) -> None:
    if enabled:
        await redis_client.set(MAINTENANCE_FLAG_KEY, "1")
    else:
        await redis_client.delete(MAINTENANCE_FLAG_KEY)


async def _move_key(old_key: str, new_key: str) -> None:
    """Rename a Redis key, merging contents when the destination exists."""
    if old_key == new_key:
        return
    if not await redis_client.exists(old_key):
        return
    if not await redis_client.exists(new_key):
        await redis_client.rename(old_key, new_key)
        return

    old_type = await redis_client.type(old_key)
    new_type = await redis_client.type(new_key)
    if old_type != new_type:
        await redis_client.delete(old_key)
        return

    if old_type == "hash":
        data = await redis_client.hgetall(old_key)
        if data:
            await redis_client.hset(new_key, mapping=data)
    elif old_type == "set":
        members = await redis_client.smembers(old_key)
        if members:
            await redis_client.sadd(new_key, *members)
    elif old_type == "list":
        values = await redis_client.lrange(old_key, 0, -1)
        if values:
            await redis_client.rpush(new_key, *reversed(values))
    elif old_type == "zset":
        members = await redis_client.zrange(old_key, 0, -1, withscores=True)
        if members:
            mapping = {member: score for member, score in members}
            await redis_client.zadd(new_key, mapping)
    else:
        value = await redis_client.get(old_key)
        if value is not None:
            await redis_client.set(new_key, value)

    await redis_client.delete(old_key)


def _should_track_path(path: str) -> bool:
    for prefix in ANALYTICS_IGNORE_PREFIXES:
        if path.startswith(prefix):
            return False
    return True


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    client = request.client
    if client and client.host:
        return client.host
    return ""


def _format_location_label(country: str, region: str, city: str) -> str:
    parts = [city, region, country]
    label = ", ".join(p for p in parts if p)
    return label or (country or "Unknown") or "Unknown"


def _format_timestamp(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ts
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _normalize_date_str(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return ""
    return dt.date().isoformat()


async def _resolve_ip_location(ip: str) -> dict[str, str]:
    default = {
        "country": "",
        "region": "",
        "city": "",
        "label": "Unknown",
    }
    if not ip:
        return default
    try:
        ip_obj = ipaddress.ip_address(ip)
        if any(
            [
                ip_obj.is_private,
                ip_obj.is_loopback,
                ip_obj.is_reserved,
                ip_obj.is_multicast,
                ip_obj.is_unspecified,
            ]
        ):
            label = "Local Network"
            return {
                "country": "",
                "region": "",
                "city": "",
                "label": label,
            }
    except ValueError:
        return default

    cache_key = f"{ANALYTICS_GEO_CACHE_PREFIX}{ip}"
    cached = await redis_client.get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city"
            )
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("status") == "success":
                    country = payload.get("country") or ""
                    region = payload.get("regionName") or ""
                    city = payload.get("city") or ""
                    label = _format_location_label(country, region, city)
                    result = {
                        "country": country,
                        "region": region,
                        "city": city,
                        "label": label,
                    }
                    await redis_client.setex(
                        cache_key, GEO_CACHE_TTL_SECONDS, json.dumps(result)
                    )
                    return result
    except Exception as exc:
        print(f"[analytics] geo lookup failed for {ip}: {exc}")

    return default


async def _record_visit(ip: str, path: str, user: str, user_agent: str = "") -> None:
    now = datetime.utcnow().isoformat()
    location = await _resolve_ip_location(ip)
    visitor_key = f"analytics:visitor:{ip or 'unknown'}"
    count = await redis_client.hincrby(visitor_key, "count", 1)
    await redis_client.hset(
        visitor_key,
        mapping={
            "ip": ip or "unknown",
            "last_seen": now,
            "country": location.get("country", ""),
            "region": location.get("region", ""),
            "city": location.get("city", ""),
            "label": location.get("label", "Unknown"),
            "last_path": path,
            "last_user": user or "",
            "user_agent": user_agent,
            "count": count,
        },
    )
    await redis_client.sadd(ANALYTICS_UNIQUE_IPS_KEY, ip or "unknown")
    await redis_client.incr(ANALYTICS_TOTAL_VISITS_KEY)
    log_entry = {
        "ip": ip or "unknown",
        "path": path,
        "timestamp": now,
        "user": user or "",
        "location": location.get("label", "Unknown"),
    }
    await redis_client.lpush(ANALYTICS_VISITOR_KEY, json.dumps(log_entry))
    await redis_client.ltrim(ANALYTICS_VISITOR_KEY, 0, ANALYTICS_VISITOR_LIMIT - 1)


async def _user_growth_series() -> tuple[list[dict[str, Any]], int]:
    keys = await redis_client.keys("user:*")
    totals: dict[str, int] = {}
    unknown = 0
    for key in keys:
        data = await redis_client.hgetall(key)
        created = _normalize_date_str(data.get("created_at", ""))
        if created:
            totals[created] = totals.get(created, 0) + 1
        else:
            unknown += 1
    total_users = len(keys)
    if not totals:
        if total_users:
            today = datetime.utcnow().date().isoformat()
            return ([{"date": today, "count": total_users}]), total_users
        return ([], 0)
    series: list[dict[str, Any]] = []
    cumulative = 0
    for date in sorted(totals.keys()):
        cumulative += totals[date]
        series.append({"date": date, "count": cumulative})
    if unknown:
        for idx in range(len(series)):
            series[idx]["count"] += unknown
    return series, total_users


async def _analytics_dashboard(page: int = 1, limit: int = 20) -> dict[str, Any]:
    total_visits_raw = await redis_client.get(ANALYTICS_TOTAL_VISITS_KEY)
    try:
        total_visits = int(total_visits_raw or 0)
    except Exception:
        total_visits = 0

    visitor_keys = await redis_client.keys("analytics:visitor:*")
    visitor_details: list[dict[str, Any]] = []
    location_totals: dict[str, int] = {}

    for key in visitor_keys:
        data = await redis_client.hgetall(key)
        if not data:
            continue
        ip = data.get("ip", key.split(":", 2)[-1])
        count_raw = data.get("count", 0)
        try:
            count = int(count_raw)
        except Exception:
            count = 0
        last_seen = _format_timestamp(data.get("last_seen", ""))
        label = data.get("label") or _format_location_label(
            data.get("country", ""),
            data.get("region", ""),
            data.get("city", ""),
        )
        location_totals[label] = location_totals.get(label, 0) + count
        visitor_details.append(
            {
                "ip": ip,
                "count": count,
                "last_seen": last_seen,
                "label": label,
                "country": data.get("country", ""),
                "region": data.get("region", ""),
                "city": data.get("city", ""),
                "last_path": data.get("last_path", ""),
                "last_user": data.get("last_user", ""),
            }
        )

    # Sort and paginate
    visitor_details.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
    total_visitors = len(visitor_details)
    start = (page - 1) * limit
    end = start + limit
    visitor_details = visitor_details[start:end]

    # Top locations (not paginated, but you could if needed)
    top_locations = [
        {"label": label, "count": count}
        for label, count in sorted(
            location_totals.items(), key=lambda x: x[1], reverse=True
        )
    ]

    raw_recent = await redis_client.lrange(ANALYTICS_VISITOR_KEY, 0, limit - 1)
    recent: list[dict[str, Any]] = []
    for raw in raw_recent:
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        entry["timestamp"] = _format_timestamp(entry.get("timestamp", ""))
        recent.append(entry)

    unique_visitors = await redis_client.scard(ANALYTICS_UNIQUE_IPS_KEY)
    user_growth, total_users = await _user_growth_series()

    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "visitor_details": visitor_details,
        "recent": recent,
        "top_locations": top_locations,
        "user_growth": user_growth,
        "total_users": total_users,
        "page": page,
        "limit": limit,
        "total_visitors": total_visitors,
    }


async def _pending_rewards_map() -> dict[str, float]:
    mapping: dict[str, float] = {}
    data = await _get_cached_data()
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if "email" in columns and "pending_reward" in columns:
        for row in rows:
            email = str(row.get("email", "")).strip().lower()
            if email:
                try:
                    mapping[email] = float(row.get("pending_reward", 0))
                except Exception:
                    mapping[email] = 0.0
    return mapping


async def _all_wallets() -> list[dict[str, Any]]:
    wallets: list[dict[str, Any]] = []
    data = await _get_cached_data()
    rows = data.get("rows", [])

    activity_start_ts, activity_end_ts = await _activity_window_bounds()
    guardians = await _guardian_emails()

    # Build lookup maps by email AND telegram (normalized)
    email_map: dict[str, dict[str, float]] = {}
    tg_map: dict[str, dict[str, float]] = {}

    for row in rows:
        try:
            pts = float(row.get("points", 0))
        except Exception:
            pts = 0.0
        try:
            rew = float(row.get("pending_reward", 0))
        except Exception:
            rew = 0.0

        stats = {"points": pts, "pending_reward": rew}

        eml = str(row.get("email", "")).strip().lower()
        if eml:
            email_map[eml] = stats

        tg = str(row.get("telegram", "")).strip()
        if tg:
            tg_norm = tg.lstrip("@").lower()
            if tg_norm:
                tg_map[tg_norm] = stats

    pad_map = await redis_client.hgetall("score_pad")

    keys = await redis_client.keys("user:*")
    for key in keys:
        email = key.split(":", 1)[1].strip().lower()
        if email not in REGISTERED_EMAILS:   # 🚨 filter unregistered
            continue

        udata = await redis_client.hgetall(key)

        tele_raw = udata.get("telegram", "")
        tele_norm = str(tele_raw).strip().lstrip("@").lower()
        tele_display = f"@{tele_norm}" if tele_norm else ""

        stats = email_map.get(email) or (tg_map.get(tele_norm) if tele_norm else None)
        if not stats:
            stats = {"points": 0.0, "pending_reward": 0.0}

        try:
            pad_val = float(pad_map.get(email, 0.0))
        except Exception:
            pad_val = 0.0

        verified_posts = await redis_client.scard(f"posts_verified:{email}")
        task_statuses = await redis_client.hvals(f"tasks:{email}")
        task_verified = any(v == "verified" for v in task_statuses)
        is_verified = (
            verified_posts > 0
            or task_verified
            or str(udata.get("verified")) == "1"
        )
        await redis_client.hset(f"user:{email}", "verified", int(is_verified))

        activity_key = f"{ACTIVITY_ZSET_PREFIX}{email}"
        weekly_posts = await redis_client.zcount(activity_key, activity_start_ts, activity_end_ts)
        is_active = weekly_posts > 0
        activity_label = "active" if is_active else "inactive"
        await redis_client.hset(f"user:{email}", "activity", activity_label)

        is_guardian = email in guardians
        if is_guardian:
            await redis_client.hset(f"user:{email}", GUARDIAN_USER_FIELD, "1")
        else:
            await redis_client.hdel(f"user:{email}", GUARDIAN_USER_FIELD)

        referrals = await _referral_entries(email)
        referral_count = sum(1 for entry in referrals if entry.get("status") != "rejected")
        await redis_client.hset(
            f"user:{email}", mapping={"referral_count": referral_count}
        )

        kyc_record = await _get_kyc_record(email)
        kyc_status = kyc_record.get("status", KYC_STATUS_NONE)
        await _set_user_kyc_status(email, kyc_status)
        kyc_updated = _format_timestamp(kyc_record.get("updated_at", ""))

        wallets.append(
            {
                "email": email,
                "wallet": udata.get("wallet", ""),
                "telegram": tele_display,
                "tg_link": f"https://t.me/{tele_norm}" if tele_norm else "",
                "points": stats["points"],
                "pending_reward": f"{stats['pending_reward']:.8f}",
                "pad": pad_val,
                "verified": is_verified,
                "verified_posts": verified_posts,
                "active": is_active,
                "activity": activity_label,
                "guardian": is_guardian,
                "referral_count": referral_count,
                "referrals": referrals,
                "kyc_status": kyc_status,
                "kyc_status_label": KYC_STATUS_LABELS.get(kyc_status, "Not Submitted"),
                "kyc_badge_class": KYC_STATUS_BADGE_CLASSES.get(
                    kyc_status, "bg-secondary"
                ),
                "kyc_updated_at": kyc_updated,
            }
        )

    return wallets


async def _all_kyc_records() -> list[dict[str, Any]]:
    keys = await redis_client.keys("kyc:*")
    records: list[dict[str, Any]] = []
    for key in keys:
        email = key.split(":", 1)[1].strip().lower()
        if not email:
            continue
        data = await redis_client.hgetall(key)
        if not data:
            continue
        status = _normalize_kyc_status(data.get("status"))
        user_data = await redis_client.hgetall(f"user:{email}")
        record = {
            "email": email,
            "status": status,
            "status_label": KYC_STATUS_LABELS.get(status, "Not Submitted"),
            "badge_class": KYC_STATUS_BADGE_CLASSES.get(status, "bg-secondary"),
            "full_name": data.get("full_name", ""),
            "country": data.get("country", ""),
            "birthdate": data.get("birthdate", ""),
            "over_18": data.get("over_18", "no"),
            "restricted_region": data.get("restricted_region", "no"),
            "pep": data.get("pep", "no"),
            "document_type": data.get("document_type", ""),
            "document_number_last4": data.get("document_number_last4", ""),
            "document_url": data.get("document_url", ""),
            "document_uploaded_at": _format_timestamp(
                data.get("document_uploaded_at", "")
            ),
            "address_line": data.get("address_line", ""),
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "postal_code": data.get("postal_code", ""),
            "self_reported_location": data.get("self_reported_location", ""),
            "additional_notes": data.get("additional_notes", ""),
            "ip": data.get("ip", ""),
            "geo_label": data.get("geo_label", ""),
            "geo_country": data.get("geo_country", ""),
            "geo_region": data.get("geo_region", ""),
            "geo_city": data.get("geo_city", ""),
            "submitted_at": _format_timestamp(data.get("submitted_at", "")),
            "updated_at": _format_timestamp(data.get("updated_at", "")),
            "reviewed_at": _format_timestamp(data.get("reviewed_at", "")),
            "reviewed_by": data.get("reviewed_by", ""),
            "rejection_reason": data.get("rejection_reason", ""),
            "admin_notes": data.get("admin_notes", ""),
            "profile_name": user_data.get("name", ""),
            "profile_telegram": user_data.get("telegram", ""),
        }
        record["updated_at_raw"] = data.get("updated_at", "")
        records.append(record)
    records.sort(
        key=lambda item: (
            KYC_STATUS_ORDER.get(item.get("status"), 99),
            item.get("updated_at_raw", ""),
            item.get("email", ""),
        )
    )
    return records


async def _all_posts() -> dict[str, dict[str, Any]]:
    """Return pending posts grouped by user email with Telegram/pad info."""
    posts: dict[str, dict[str, Any]] = {}
    pad_map = await redis_client.hgetall("score_pad")
    keys = await redis_client.keys("posts:*")
    for key in keys:
        email = key.split(":", 1)[1].strip().lower()
        urls = await redis_client.lrange(key, 0, -1)
        verified = await redis_client.smembers(f"posts_verified:{email}")
        safe_verified = {str(v).strip() for v in verified}
        pending = [
            {"url": str(u).strip()}
            for u in urls
            if u and str(u).strip() not in safe_verified
        ]
        if pending:
            udata = await redis_client.hgetall(f"user:{email}")
            tele_raw = udata.get("telegram", "")
            tele_norm = str(tele_raw).strip().lstrip("@").lower()
            tele = f"@{tele_norm}" if tele_norm else ""
            tg_link = f"https://t.me/{tele_norm}" if tele_norm else ""
            try:
                pad_val = float(pad_map.get(email, 0.0))
            except Exception:
                pad_val = 0.0
            posts[email] = {
                "urls": pending,
                "telegram": tele,
                "tg_link": tg_link,
                "pad": pad_val,
                "count": len(pending),
            }
    return posts


async def _all_verified_posts(include_email: bool = False) -> list[dict[str, str]]:
    """Return list of verified posts with associated wallet and Telegram."""
    entries: list[dict[str, str]] = []
    keys = await redis_client.keys("posts_verified:*")
    for key in keys:
        email = key.split(":", 1)[1].strip().lower()
        urls = await redis_client.smembers(key)
        udata = await redis_client.hgetall(f"user:{email}")
        tele_raw = udata.get("telegram", "")
        tele_norm = str(tele_raw or "").strip().lstrip("@").lower()
        telegram = f"@{tele_norm}" if tele_norm else ""
        tg_link = f"https://t.me/{tele_norm}" if tele_norm else ""
        wallet = str(udata.get("wallet", "") or "")
        for raw_url in urls:
            url = str(raw_url or "").strip()
            if not url:
                continue
            entry: dict[str, str] = {
                "url": url,
                "telegram": telegram,
                "tg_link": tg_link,
                "wallet": wallet,
            }
            if include_email:
                entry["email"] = email
            entries.append(entry)
    return entries

async def _all_tasks() -> dict[str, dict[str, str]]:
    tasks: dict[str, dict[str, str]] = {}
    keys = await redis_client.keys("tasks:*")
    for key in keys:
        email = key.split(":", 1)[1]
        tasks[email] = await redis_client.hgetall(key)
    return tasks


async def _pending_proposals() -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    keys = await redis_client.keys("proposal:*")
    for key in keys:
        data = await redis_client.hgetall(key)
        if data.get("status") == "pending":
            pid = key.split(":", 1)[1]
            proposals.append(
                {
                    "id": pid,
                    "title": data.get("title", ""),
                    "content": data.get("content", ""),
                    "email": data.get("email", ""),
                    "telegram": data.get("telegram", ""),
                    "wallet": data.get("wallet", ""),
                }
            )
    return proposals


async def _active_proposals(user_email: str | None) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    keys = await redis_client.keys("proposal:*")
    for key in keys:
        data = await redis_client.hgetall(key)
        if data.get("status") != "active":
            continue
        pid = key.split(":", 1)[1]
        yes_key = f"proposal_votes_yes:{pid}"
        no_key = f"proposal_votes_no:{pid}"
        yes = await redis_client.scard(yes_key)
        no = await redis_client.scard(no_key)
        user_vote = None
        if user_email:
            if await redis_client.sismember(yes_key, user_email):
                user_vote = "yes"
            elif await redis_client.sismember(no_key, user_email):
                user_vote = "no"
        proposals.append(
            {
                "id": pid,
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "founder_wallet": data.get("wallet", ""),
                "funding_wallet": data.get("funding_wallet", ""),
                "yes": yes,
                "no": no,
                "user_vote": user_vote,
            }
        )
    return proposals

async def _all_recoveries() -> list[dict[str, str]]:
    recoveries: list[dict[str, str]] = []
    keys = await redis_client.keys("recovery:*")
    for key in keys:
        raw = await redis_client.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        recoveries.append(
            {
                "email": data.get("email", ""),
                "code": data.get("code", ""),
                "telegram": data.get("telegram", ""),
                "tg_link": data.get("tg_link"),
            }
        )
    return recoveries

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def _bootstrap_pending_review() -> None:
    await _ensure_existing_ambassadors_pending()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@app.middleware("http")
async def analytics_middleware(request: Request, call_next):
    guard = await _maintenance_guard(request)
    if guard:
        return guard
    response = await call_next(request)
    path = request.url.path
    if not _should_track_path(path):
        return response
    try:
        ip = _extract_client_ip(request)
        email = await _current_email(request)
        is_admin = await _current_admin(request)
        user_label = email or ("admin" if is_admin else "")
        user_agent = request.headers.get("user-agent", "")
        await _record_visit(ip, path, user_label, user_agent)
    except Exception as exc:
        print(f"[analytics] failed to record visit for {path}: {exc}")
    return response


def _normalize_handle(handle: str, *, lower: bool = True) -> str:
    h = str(handle or "").strip()
    if not h:
        return ""
    h = h.lstrip("@")
    if lower:
        h = h.lower()
    return f"@{h}" if h else ""


def _normalize_telegram(handle: str) -> str:
    return _normalize_handle(handle, lower=True)


def _generate_referral_code_value() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(REFERRAL_CODE_LENGTH))


async def _lookup_referrer(code: str) -> str | None:
    code_norm = str(code or "").strip().upper()
    if not code_norm:
        return None
    owner = await redis_client.get(f"{REFERRAL_CODE_KEY_PREFIX}{code_norm}")
    if owner:
        return str(owner).strip().lower()
    return None


async def _ensure_referral_code(email: str) -> str:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return ""
    key = f"user:{email_norm}"
    data = await redis_client.hgetall(key)
    existing = str(data.get("referral_code", "")).strip().upper()
    if existing:
        owner = await redis_client.get(f"{REFERRAL_CODE_KEY_PREFIX}{existing}")
        if owner and str(owner).strip().lower() == email_norm:
            if existing != data.get("referral_code", ""):
                await redis_client.hset(key, mapping={"referral_code": existing})
            return existing
        if not owner:
            pipe = redis_client.pipeline()
            pipe.set(f"{REFERRAL_CODE_KEY_PREFIX}{existing}", email_norm)
            pipe.hset(key, mapping={"referral_code": existing})
            await pipe.execute()
            return existing
    # generate fresh code
    while True:
        code = _generate_referral_code_value()
        owner = await redis_client.get(f"{REFERRAL_CODE_KEY_PREFIX}{code}")
        if not owner:
            break
    pipe = redis_client.pipeline()
    pipe.hset(key, mapping={"referral_code": code})
    pipe.set(f"{REFERRAL_CODE_KEY_PREFIX}{code}", email_norm)
    await pipe.execute()
    return code


async def _record_referral(referrer_email: str, referred_email: str, telegram: str, joined_at: str) -> None:
    referrer_norm = str(referrer_email or "").strip().lower()
    referred_norm = str(referred_email or "").strip().lower()
    if not referrer_norm or not referred_norm:
        return
    payload = {
        "email": referred_norm,
        "telegram": str(telegram or ""),
        "joined_at": joined_at,
        "status": "pending",
    }
    key = f"{REFERRALS_HASH_PREFIX}{referrer_norm}"
    await redis_client.hset(key, referred_norm, json.dumps(payload))
    entries = await _referral_entries(referrer_norm)
    count = sum(1 for entry in entries if entry.get("status") != "rejected")
    await redis_client.hset(
        f"user:{referrer_norm}", mapping={"referral_count": count}
    )


async def _referral_entries(email: str) -> list[dict[str, str]]:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return []
    raw_entries = await redis_client.hgetall(f"{REFERRALS_HASH_PREFIX}{email_norm}")
    entries: list[dict[str, str]] = []
    for raw_email, raw_payload in raw_entries.items():
        try:
            data = json.loads(raw_payload)
        except Exception:
            data = {}
        joined_at = str(data.get("joined_at", ""))
        status = str(data.get("status", "pending")) or "pending"
        entries.append(
            {
                "email": str(data.get("email", raw_email)),
                "telegram": str(data.get("telegram", "")),
                "joined_at": joined_at,
                "joined_at_display": _format_timestamp(joined_at),
                "status": status,
                "approved_at": str(data.get("approved_at", "")),
                "rejected_at": str(data.get("rejected_at", "")),
            }
        )
    entries.sort(key=lambda item: item.get("joined_at", ""), reverse=True)
    return entries


async def _set_referral_status(
    referrer_email: str, referred_email: str, status: str
) -> None:
    """Update referral status safely. Never delete; always preserve record history."""

    referrer_norm = str(referrer_email or "").strip().lower()
    referred_norm = str(referred_email or "").strip().lower()
    if not referrer_norm or not referred_norm:
        return

    key = f"{REFERRALS_HASH_PREFIX}{referrer_norm}"
    raw_payload = await redis_client.hget(key, referred_norm)
    try:
        payload = json.loads(raw_payload) if raw_payload else {}
    except Exception:
        payload = {}

    # Always preserve core fields
    payload["email"] = referred_norm
    payload["status"] = status
    payload["last_status_change"] = datetime.utcnow().isoformat()

    # Update timestamps based on status, never delete record
    if status == "approved":
        payload["approved_at"] = datetime.utcnow().isoformat()
        payload.pop("rejected_at", None)
    elif status == "rejected":
        payload["rejected_at"] = datetime.utcnow().isoformat()
        payload.pop("approved_at", None)
    elif status == "pending":
        # Clear other timestamps if reverting to pending
        payload.pop("approved_at", None)
        payload.pop("rejected_at", None)

    # ✅ Always write back the updated payload — no deletes ever
    await redis_client.hset(key, referred_norm, json.dumps(payload))

    # ✅ Keep referral_count accurate (pending + approved only)
    entries = await _referral_entries(referrer_norm)
    active_count = sum(
        1 for entry in entries if entry.get("status") in {"pending", "approved"}
    )
    await redis_client.hset(
        f"user:{referrer_norm}", mapping={"referral_count": active_count}
    )

    print(
        f"[referrals] ✅ Updated {referred_norm} for {referrer_norm} → {status}"
    )


async def _remove_referral_entry(referrer_email: str, referred_email: str) -> None:
    referrer_norm = str(referrer_email or "").strip().lower()
    referred_norm = str(referred_email or "").strip().lower()
    if not referrer_norm or not referred_norm:
        return
    key = f"{REFERRALS_HASH_PREFIX}{referrer_norm}"
    await redis_client.hdel(key, referred_norm)
    entries = await _referral_entries(referrer_norm)
    count = sum(1 for entry in entries if entry.get("status") != "rejected")
    await redis_client.hset(
        f"user:{referrer_norm}", mapping={"referral_count": count}
    )


def _register_email_record(email: str) -> None:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return

    REGISTERED_EMAILS.add(email_norm)

    path = Path(REGISTRATIONS_CSV)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: set[str] = set()
    exists = path.exists()
    if exists:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                value = line.strip().lower()
                if value:
                    existing.add(value)

    if email_norm in existing:
        return

    header_needed = not exists
    if exists and not header_needed:
        header_needed = path.stat().st_size == 0
    mode = "a" if exists else "w"
    with path.open(mode, encoding="utf-8") as fh:
        if header_needed:
            fh.write("ambassadors\n")
        fh.write(f"{email_norm}\n")


def _unregister_email_record(email: str) -> None:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return

    REGISTERED_EMAILS.discard(email_norm)

    path = Path(REGISTRATIONS_CSV)
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as fh:
        rows = [line.rstrip("\n") for line in fh]

    if not rows:
        return

    header = rows[0] or "ambassadors"
    remaining = [row for row in rows[1:] if row.strip().lower() != email_norm]

    if len(remaining) == len(rows) - 1:
        with path.open("w", encoding="utf-8") as fh:
            fh.write(f"{header}\n")
            for row in remaining:
                value = row.strip()
                if value:
                    fh.write(f"{value}\n")


async def _ensure_existing_ambassadors_pending() -> None:
    """Mark all existing ambassadors as pending for a one-time review sweep (safe, no deletes)."""

    if await redis_client.get(PENDING_VERIFICATION_MIGRATION_KEY):
        if not PENDING_VERIFICATION_MIGRATION_SENTINEL.exists():
            try:
                MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
                PENDING_VERIFICATION_MIGRATION_SENTINEL.write_text("redis", encoding="utf-8")
            except Exception:
                pass
        return

    if PENDING_VERIFICATION_MIGRATION_SENTINEL.exists():
        await redis_client.set(
            PENDING_VERIFICATION_MIGRATION_KEY, datetime.utcnow().isoformat(), nx=True
        )
        return

    try:
        processed = skipped = 0

        async for key in redis_client.scan_iter("user:*"):
            email_part = key.split(":", 1)[1].strip().lower()

            # ✅ Skip numeric-only keys
            if email_part.isdigit():
                print(f"[migration] skipping numeric key: {key}")
                skipped += 1
                continue

            # ✅ Type check
            key_type = await redis_client.type(key)
            key_type_str = (
                key_type.decode() if isinstance(key_type, (bytes, bytearray)) else str(key_type)
            )
            if key_type_str != "hash":
                print(f"[migration] skipping non-hash key: {key} (type={key_type_str})")
                skipped += 1
                continue

            # ✅ Always mark as unverified
            await redis_client.hset(key, mapping={"verified": 0})

            # 🆕 Backfill default referrer if missing
            ref_by = await redis_client.hget(key, "referred_by")
            if not ref_by:
                await redis_client.hset(key, mapping={"referred_by": "interchained@gmail.com"})

            processed += 1

        # ✅ Process referrals safely
        async for key in redis_client.scan_iter(f"{REFERRALS_HASH_PREFIX}*"):
            key_type = await redis_client.type(key)
            key_type_str = (
                key_type.decode() if isinstance(key_type, (bytes, bytearray)) else str(key_type)
            )
            if key_type_str != "hash":
                print(f"[migration] skipping non-hash referral key: {key} (type={key_type_str})")
                continue

            referrer = key.split(":", 1)[1].strip().lower()
            raw_map = await redis_client.hgetall(key)
            updates: dict[str, str] = {}

            for referred_email, raw in raw_map.items():
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                status = str(payload.get("status", "")).strip().lower()
                if status != "pending":
                    payload["status"] = "pending"
                    # ✅ Don't pop anything — just overwrite status
                    updates[referred_email] = json.dumps(payload)

            if updates:
                await redis_client.hset(key, mapping=updates)

            if referrer:
                entries = await _referral_entries(referrer)
                count = sum(1 for entry in entries if entry.get("status") != "rejected")
                await redis_client.hset(f"user:{referrer}", mapping={"referral_count": count})

        # ✅ Write sentinel
        await redis_client.set(
            PENDING_VERIFICATION_MIGRATION_KEY, datetime.utcnow().isoformat()
        )
        try:
            MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
            PENDING_VERIFICATION_MIGRATION_SENTINEL.write_text(
                datetime.utcnow().isoformat(), encoding="utf-8"
            )
        except Exception:
            print("[migration] failed to persist sentinel flag to disk")

        print(f"[migration] ✅ Finished. Processed {processed} hashes, skipped {skipped} keys.")

    except Exception as exc:
        print(f"[migration] failed to queue existing ambassadors for review: {exc}")
        

async def _pending_referrals() -> list[dict[str, Any]]:
    """Return all pending and rejected referrals (exclude only approved)."""
    pending: list[dict[str, Any]] = []

    async for key in redis_client.scan_iter("user:*"):
        email = key.split(":", 1)[1].strip().lower()
        data = await redis_client.hgetall(key)
        if not data:
            continue

        # ✅ Skip approved users
        if str(data.get("verified", "0")) == "1":
            continue

        # 👇 Determine status from user hash or referral payload
        status = "pending"
        if str(data.get("rejected", "0")) == "1":
            status = "rejected"

        referred_by = str(data.get("referred_by", "")).strip().lower()
        created_at = str(data.get("created_at", ""))
        joined_at = str(data.get("referred_at", "")) or created_at
        referral_payload: dict[str, Any] | None = None

        if referred_by:
            raw = await redis_client.hget(
                f"{REFERRALS_HASH_PREFIX}{referred_by}", email
            )
            if raw:
                try:
                    referral_payload = json.loads(raw)
                except Exception:
                    referral_payload = None

        if referral_payload:
            joined_at = str(referral_payload.get("joined_at", joined_at)) or joined_at
            status = str(referral_payload.get("status", status)) or status

        ref_label = referred_by
        if referred_by:
            ref_profile = await redis_client.hgetall(f"user:{referred_by}")
            tg = str(ref_profile.get("telegram", ""))
            if tg:
                ref_label = tg

        pending.append(
            {
                "email": email,
                "telegram": str(data.get("telegram", "")),
                "wallet": str(data.get("wallet", "")),
                "twitter": str(data.get("twitter", "")),
                "discord": str(data.get("discord", "")),
                "referred_by": referred_by,
                "referred_by_label": ref_label,
                "status": status,  # ✅ Now includes "pending" or "rejected"
                "created_at": created_at,
                "joined_at": joined_at,
                "joined_at_display": _format_timestamp(joined_at),
                "email_opt_in": str(data.get("email_opt_in", "0")) in {"1", "true", "yes"},
            }
        )

    # ✅ Sort with rejected at the bottom
    pending.sort(
        key=lambda item: (item.get("status") == "rejected", item.get("joined_at", "")),
        reverse=True,
    )
    return pending


def _ensure_leaderboard_entry(email: str, telegram: str) -> None:
    email_norm = str(email or "").strip().lower()

    # ✅ Safety: must be a valid email
    if not email_norm or "@" not in email_norm:
        print(f"[leaderboard] ⚠️ Skipping invalid email: {email}")
        return

    tele_norm = _normalize_telegram(telegram)
    username = tele_norm.lstrip("@") if tele_norm else email_norm.split("@")[0]

    path = Path(CSV_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "name",
        "telegram",
        "points",
        "tier",
        "posts",
        "engagements",
        "referrals",
        "email",
    ]

    # ✅ Load & sanitize all rows
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames:
                fieldnames = reader.fieldnames
            for row in reader:
                clean_row = {k: (row.get(k, "") or "").strip() for k in fieldnames}
                rows.append(clean_row)

    # ✅ Deduplicate by email (last seen wins)
    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        row_email = (row.get("email") or "").strip().lower()
        if "@" not in row_email:
            continue
        deduped[row_email] = row  # last one wins

    # ✅ Update or create this entry
    entry = deduped.get(email_norm, {key: "" for key in fieldnames})
    entry.update({
        "email": email_norm,
        "telegram": tele_norm or entry.get("telegram", ""),
        "name": username or entry.get("name", ""),
    })

    # ✅ Defaults: tier and numeric columns
    if not str(entry.get("tier", "")).strip():
        entry["tier"] = "Ambassador"
    for key in ("points", "posts", "engagements", "referrals"):
        if not str(entry.get(key, "")).strip():
            entry[key] = "0"

    # ✅ Put back into deduped dict
    deduped[email_norm] = entry

    # ✅ Final dedupe sweep: sort by email & write clean CSV
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(deduped.values(), key=lambda r: r["email"]):
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"[leaderboard] ✅ Entry ensured and deduped for {email_norm}")


def _remove_leaderboard_entry(email: str) -> bool:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return False

    path = Path(CSV_PATH)
    if not path.exists():
        return False

    removed = False
    rows: list[dict[str, str]] = []
    fieldnames: list[str] = []

    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            row_email = str(row.get("email", "")).strip().lower()
            if row_email == email_norm:
                removed = True
                continue
            rows.append(dict(row))

    if not removed:
        return False

    if not fieldnames:
        fieldnames = [
            "name",
            "telegram",
            "points",
            "tier",
            "posts",
            "engagements",
            "referrals",
            "email",
        ]

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    return True


# serve /favicon.ico at the root
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/login")
async def login_form(request: Request, msg: str | None = None) -> Any:
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "", "msg": msg or ""}
    )


@app.post("/login")
async def login(
    request: Request, email: str = Form(...), password: str = Form(...)
) -> Any:
    email_norm = email.strip().lower()
    stored = await redis_client.hgetall(f"user:{email_norm}")
    if not stored and email_norm not in REGISTERED_EMAILS:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Email not registered", "msg": ""}
        )
    if not stored or stored.get("password") != _hash_password(password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials", "msg": ""}
        )
    if str(stored.get("verified", "0")) != "1":
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Your registration is pending admin approval.",
                "msg": "",
            },
        )
    if email_norm not in REGISTERED_EMAILS:
        _register_email_record(email_norm)
    token = secrets.token_urlsafe(32)
    await redis_client.set(f"session:{token}", email_norm, ex=SESSION_TTL_SECONDS)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session", token, httponly=True, max_age=SESSION_TTL_SECONDS)
    return response


@app.get("/forgot")
async def forgot_form(request: Request) -> Any:
    """Render forgot password form."""
    return templates.TemplateResponse(
        "forgot.html", {"request": request, "email": "", "submitted": False}
    )


@app.post("/forgot")
async def forgot_submit(request: Request, email: str = Form(...)) -> Any:
    """Generate recovery hash for a given email."""
    email_norm = email.strip().lower()
    telegram = ""
    tg_link: str | None = None
    try:
        df = pd.read_csv(CSV_PATH)
        df.columns = [c.strip().lower() for c in df.columns]
        if "email" in df.columns:
            row = df[df["email"].astype(str).str.lower() == email_norm]
        else:
            row = pd.DataFrame()
        if not row.empty:
            telegram = str(row.iloc[0].get("telegram", "")).strip()
    except Exception:
        telegram = ""
    telegram_norm = _normalize_telegram(telegram) if telegram else ""
    if telegram_norm:
        tg_link = f"https://t.me/{telegram_norm.lstrip('@')}"
    code = "IGP" + hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    data = {
        "email": email_norm,
        "telegram": telegram_norm,
        "tg_link": tg_link,
        "code": code,
    }
    await redis_client.set(
        f"recovery:{email_norm}", json.dumps(data), ex=RECOVERY_TTL_SECONDS
    )
    return templates.TemplateResponse(
        "forgot.html",
        {"request": request, "email": email_norm, "submitted": True},
    )


@app.get("/register")
async def register_form(request: Request) -> Any:
    referral_code = request.query_params.get("ref", "").strip()
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "error": "",
            "email": request.query_params.get("email", ""),
            "wallet": request.query_params.get("wallet", ""),
            "telegram": request.query_params.get("telegram", ""),
            "twitter": request.query_params.get("twitter", ""),
            "discord": request.query_params.get("discord", ""),
            "referral": referral_code,
            "email_opt_in": False,
        },
    )


@app.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    telegram: str = Form(...),
    wallet: str = Form(...),
    twitter: str = Form(""),
    discord: str = Form(""),
    referral_code: str = Form(""),
    email_opt_in: str = Form(""),
) -> Any:
    email_norm = email.strip().lower()
    telegram_norm = _normalize_telegram(telegram)
    twitter_norm = _normalize_handle(twitter)
    discord_clean = str(discord or "").strip()
    opt_in = str(email_opt_in or "").strip().lower() in {"1", "true", "yes", "on"}
    referral_input = str(referral_code or "").strip()

    form_context = {
        "request": request,
        "error": "",
        "email": email,
        "wallet": wallet,
        "telegram": telegram,
        "twitter": twitter,
        "discord": discord,
        "referral": referral_input,
        "email_opt_in": opt_in,
    }
    key = f"user:{email_norm}"
    existing = await redis_client.hgetall(key)
    has_created = "created_at" in existing
    try:
        existing_referral_count = int(existing.get("referral_count", 0))
    except Exception:
        existing_referral_count = 0

    existing_referrer = str(existing.get("referred_by", "")).strip().lower()
    referrer_email = existing_referrer
    new_referral = None
    if referral_input:
        new_referral = await _lookup_referrer(referral_input)
        if not new_referral:
            return templates.TemplateResponse(
                "register.html",
                {**form_context, "error": "Referral code not recognized"},
            )
        if new_referral == email_norm:
            return templates.TemplateResponse(
                "register.html",
                {**form_context, "error": "You cannot refer yourself"},
            )
    if not existing_referrer and new_referral:
        referrer_email = new_referral

    if email_norm not in REGISTERED_EMAILS and not referrer_email:
        return templates.TemplateResponse(
            "register.html",
            {**form_context, "error": "Email not permitted"},
        )

    now_iso = datetime.utcnow().isoformat()
    await redis_client.hset(
        key,
        mapping={
            "password": _hash_password(password),
            "wallet": wallet.strip(),
            "telegram": telegram_norm,
            "twitter": twitter_norm,
            "discord": discord_clean,
            "email_opt_in": 1 if opt_in else 0,
            "referral_count": existing_referral_count,
            "verified": 0,
            **({"created_at": now_iso} if not has_created else {}),
            **(
                {"referred_by": referrer_email, "referred_at": now_iso}
                if referrer_email and not existing_referrer
                else {}
            ),
        },
    )
    referral_code_value = await _ensure_referral_code(email_norm)
    if referral_code_value:
        await redis_client.hset(
            key, mapping={"referral_code": referral_code_value}
        )

    if referrer_email and referrer_email != existing_referrer:
        await _record_referral(
            referrer_email, email_norm, telegram_norm, now_iso
        )

    return RedirectResponse(
        "/login?msg=Registration+submitted+for+approval",
        status_code=303,
    )


@app.get("/wallet")
async def wallet_form(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    profile_ctx = await _build_profile_account_context(request, email)
    kyc_status = profile_ctx["kyc_status"]
    wallet_msg = request.query_params.get("wallet_msg", "")
    wallet_error = request.query_params.get("wallet_err", "")
    profile_msg = request.query_params.get("profile_msg", "")
    profile_error = request.query_params.get("profile_err", "")
    kyc_msg = request.query_params.get("kyc_msg", "")
    kyc_error = request.query_params.get("kyc_err", "")
    return templates.TemplateResponse(
        "wallet.html",
        {
            "request": request,
            "wallet_error": wallet_error,
            "wallet_msg": wallet_msg,
            "profile_msg": profile_msg,
            "profile_error": profile_error,
            "kyc_msg": kyc_msg,
            "kyc_error": kyc_error,
            "user_profile": profile_ctx["user_profile"],
            "wallet": profile_ctx["wallet"],
            "kyc_status": kyc_status,
            "kyc_status_label": profile_ctx["kyc_status_label"],
            "kyc_badge_class": profile_ctx["kyc_badge_class"],
            "kyc": profile_ctx["kyc"],
            "client_ip": profile_ctx["client_ip"],
            "client_location": profile_ctx["client_location"],
            "today_iso": profile_ctx["today_iso"],
            "show_kyc_toast": profile_ctx["show_kyc_toast"],
        },
    )


@app.post("/wallet")
async def wallet_update(request: Request, wallet: str = Form(...)) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    await redis_client.hset(f"user:{email}", mapping={"wallet": wallet.strip()})
    msg = quote_plus("Wallet address updated")
    return RedirectResponse(f"/wallet?wallet_msg={msg}#wallet", status_code=303)


@app.post("/profile/meta")
async def profile_meta_update(
    request: Request,
    name: str = Form(""),
    telegram: str = Form(""),
    twitter: str = Form(""),
    discord: str = Form(""),
    bio: str = Form(""),
    language: str = Form(""),
    timezone: str = Form(""),
) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    name_clean = _safe_text(name).strip()
    telegram_norm = _normalize_telegram(telegram)
    twitter_norm = _normalize_handle(twitter)
    discord_clean = _safe_text(discord).strip()
    bio_clean = _safe_text(bio).strip()
    if len(bio_clean) > 500:
        bio_clean = bio_clean[:500]
    language_clean = _safe_text(language).strip().lower()
    timezone_clean = _safe_text(timezone).strip()
    await redis_client.hset(
        f"user:{email}",
        mapping={
            "name": name_clean,
            "telegram": telegram_norm,
            "twitter": twitter_norm,
            "discord": discord_clean,
            "bio": bio_clean,
            "preferred_language": language_clean,
            "preferred_timezone": timezone_clean,
            "profile_updated_at": datetime.utcnow().isoformat(),
        },
    )
    msg = quote_plus("Profile preferences updated")
    return RedirectResponse(f"/wallet?profile_msg={msg}#profile", status_code=303)


@app.post("/profile/kyc")
async def profile_kyc_update(
    request: Request,
    full_name: str = Form(...),
    country: str = Form(...),
    birthday: str = Form(...),
    over_18: str | None = Form(None),
    restricted_region: str | None = Form(None),
    pep: str | None = Form(None),
    document_type: str = Form(""),
    document_number_last4: str = Form(""),
    address_line: str = Form(""),
    city: str = Form(""),
    region: str = Form(""),
    postal_code: str = Form(""),
    self_reported_location: str = Form(""),
    additional_notes: str = Form(""),
    document: UploadFile | None = File(None),
) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    name_clean = _safe_text(full_name).strip()
    country_clean = _safe_text(country).strip()
    notes_clean = _safe_text(additional_notes).strip()
    if len(notes_clean) > 1000:
        notes_clean = notes_clean[:1000]
    location_manual = _safe_text(self_reported_location).strip()
    if len(location_manual) > 200:
        location_manual = location_manual[:200]
    if not name_clean:
        err = quote_plus("Full name is required for KYC")
        return RedirectResponse(f"/wallet?kyc_err={err}#kyc", status_code=303)
    if not country_clean:
        err = quote_plus("Country is required for KYC")
        return RedirectResponse(f"/wallet?kyc_err={err}#kyc", status_code=303)

    ok, birthdate_iso = _parse_birthdate(birthday)
    if not ok:
        err = quote_plus(birthdate_iso)
        return RedirectResponse(f"/wallet?kyc_err={err}#kyc", status_code=303)

    existing = await _get_kyc_record(email)
    document_url = existing.get("document_url", "")
    if document and getattr(document, "filename", ""):
        success, uploaded_url, upload_error = await _upload_temp_document(document)
        if not success:
            err = quote_plus(upload_error or "Document upload failed")
            return RedirectResponse(f"/wallet?kyc_err={err}#kyc", status_code=303)
        document_url = uploaded_url
        document_uploaded_at = datetime.utcnow().isoformat()
    else:
        document_uploaded_at = existing.get("document_uploaded_at", "")

    ip = _extract_client_ip(request)
    geo = await _resolve_ip_location(ip)
    now_iso = datetime.utcnow().isoformat()
    kyc_key = f"kyc:{email}"
    mapping = {
        "status": KYC_STATUS_PENDING,
        "full_name": name_clean,
        "country": country_clean,
        "birthdate": birthdate_iso,
        "over_18": _bool_flag(over_18),
        "restricted_region": _bool_flag(restricted_region),
        "pep": _bool_flag(pep),
        "document_type": _safe_text(document_type).strip(),
        "document_number_last4": _safe_text(document_number_last4).strip(),
        "address_line": _safe_text(address_line).strip(),
        "city": _safe_text(city).strip(),
        "region": _safe_text(region).strip(),
        "postal_code": _safe_text(postal_code).strip(),
        "self_reported_location": location_manual,
        "additional_notes": notes_clean,
        "ip": ip,
        "geo_country": geo.get("country", ""),
        "geo_region": geo.get("region", ""),
        "geo_city": geo.get("city", ""),
        "geo_label": geo.get("label", ""),
        "submitted_at": now_iso,
        "updated_at": now_iso,
        "reviewed_at": "",
        "reviewed_by": "",
        "rejection_reason": "",
        "admin_notes": existing.get("admin_notes", ""),
    }
    if document_url:
        mapping["document_url"] = document_url
    if document_url and document_uploaded_at:
        mapping["document_uploaded_at"] = document_uploaded_at

    await redis_client.hset(kyc_key, mapping=mapping)
    await _set_user_kyc_status(email, KYC_STATUS_PENDING)

    msg = quote_plus("KYC details submitted for review")
    return RedirectResponse(f"/wallet?kyc_msg={msg}#kyc", status_code=303)


@app.get("/referrals")
async def referrals_dashboard(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    referral_code = await _ensure_referral_code(email)
    register_url = str(request.url_for("register_form"))
    referral_link = f"{register_url}?ref={referral_code}" if referral_code else register_url

    entries = await _referral_entries(email)
    referral_count = sum(1 for entry in entries if entry.get("status") != "rejected")
    pending_count = sum(1 for entry in entries if entry.get("status") == "pending")
    approved_count = sum(1 for entry in entries if entry.get("status") == "approved")

    user_data = await redis_client.hgetall(f"user:{email}")
    referred_by = str(user_data.get("referred_by", ""))
    referred_by_label = referred_by
    if referred_by:
        ref_profile = await redis_client.hgetall(f"user:{referred_by}")
        if ref_profile.get("telegram"):
            referred_by_label = ref_profile.get("telegram")

    return templates.TemplateResponse(
        "referrals.html",
        {
            "request": request,
            "referral_code": referral_code,
            "referral_link": referral_link,
            "referral_count": referral_count,
            "referrals_pending": pending_count,
            "referrals_approved": approved_count,
            "referrals": entries,
            "referred_by": referred_by_label,
        },
    )


def _transfer_totals(history: list[dict[str, Any]]) -> dict[str, float]:
    sent = sum(float(entry.get("amount", 0) or 0) for entry in history if entry.get("direction") == "sent")
    received = sum(
        float(entry.get("amount", 0) or 0) for entry in history if entry.get("direction") == "received"
    )
    return {"sent": sent, "received": received}


@app.get("/transfers")
async def transfers_page(request: Request, success: str | None = None, error: str | None = None) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    profile = await _ambassador_entry_by_email(email)
    if not profile:
        history = []
        totals = {"sent": 0.0, "received": 0.0}
        return templates.TemplateResponse(
            "transfers.html",
            {
                "request": request,
                "error": error or "No leaderboard profile found. Contact an administrator.",
                "success": success or "",
                "available_points": 0.0,
                "staked_amount": await _staked_amount(email),
                "history": history,
                "totals": totals,
            },
        )

    history = await _transfer_history(email)
    totals = _transfer_totals(history)
    balances = await _stake_balances(email, profile=profile)
    pad_balance = balances["scorepad"]
    available_points = balances["available"]
    staked_amount = balances["staked"]
    success_msg = success or request.query_params.get("success", "")
    error_msg = error or request.query_params.get("error", "")

    return templates.TemplateResponse(
        "transfers.html",
        {
            "request": request,
            "error": error_msg,
            "success": success_msg,
            "available_points": available_points,
            "profile": profile,
            "history": history,
            "totals": totals,
            "scorepad_balance": pad_balance,
            "staked_amount": staked_amount,
        },
    )


@app.post("/transfers")
async def transfers_submit(
    request: Request,
    destination: str = Form(...),
    amount: str = Form(...),
) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    error_message = ""
    try:
        amount_value = float(str(amount).strip())
    except Exception:
        amount_value = -1.0
    if amount_value <= 0:
        error_message = "Enter a positive amount to transfer."

    source_profile = await _ambassador_entry_by_email(email)
    if not source_profile:
        error_message = "Unable to locate your leaderboard profile."

    destination_profile = None
    if not error_message:
        destination_profile = await _ambassador_entry_by_identifier(destination)
        if not destination_profile:
            error_message = "Destination ambassador not found."
        elif destination_profile.get("guardian"):
            error_message = "Guardians cannot receive scorepad transfers."

    if not error_message and destination_profile.get("email") == email:
        error_message = "You cannot transfer points to yourself."

    if error_message:
        return await transfers_page(request, error=error_message)

    source_balances = await _stake_balances(email, profile=source_profile)
    available_points = source_balances["available"]
    if amount_value > available_points:
        return await transfers_page(
            request,
            error="Transfer exceeds your available points.",
        )

    receiver_email = destination_profile.get("email") or ""
    if not receiver_email:
        return await transfers_page(request, error="Destination ambassador is missing an email. Contact support.")

    dest_balances = await _stake_balances(receiver_email, profile=destination_profile)
    receiver_points_before = dest_balances["available"]

    pipe = redis_client.pipeline()
    pipe.hincrbyfloat("score_pad", email, -amount_value)
    pipe.hincrbyfloat("score_pad", receiver_email, amount_value)
    await pipe.execute()

    try:
        await _load_csv()
    except Exception as exc:
        print(f"[transfer] failed to refresh leaderboard cache: {exc}")

    await _record_transfer(
        source_profile,
        destination_profile,
        amount_value,
        sender_total_before=available_points,
        receiver_total_before=receiver_points_before,
    )

    dest_display = destination_profile.get("telegram") or destination_profile.get("email_display") or receiver_email
    success_message = f"Transferred {amount_value:.2f} points to {dest_display}"
    return RedirectResponse(f"/transfers?success={quote_plus(success_message)}", status_code=303)


@app.get("/p2p")
async def p2p_store(
    request: Request,
    success: str | None = None,
    error: str | None = None,
) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    profile = await _ambassador_entry_by_email(email)
    balances = await _stake_balances(email, profile=profile)
    scorepad_balance = balances.get("scorepad", 0.0)
    staked_amount = balances.get("staked", 0.0)
    total_points = balances.get("total", 0.0)
    prizes = await _p2p_prizes()
    history = await _p2p_user_history(email)
    success_msg = success or request.query_params.get("success", "")
    error_msg = error or request.query_params.get("error", "")

    return templates.TemplateResponse(
        "p2p.html",
        {
            "request": request,
            "profile": profile,
            "prizes": prizes,
            "history": history,
            "success": success_msg,
            "error": error_msg,
            "scorepad_balance": scorepad_balance,
            "staked_amount": staked_amount,
            "total_points": total_points,
        },
    )


@app.post("/p2p/redeem")
async def p2p_redeem(
    request: Request,
    prize_id: str = Form(...),
    note: str = Form(""),
) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    prize = await _p2p_prize(prize_id)
    if not prize or not prize.get("active"):
        return await p2p_store(request, error="That prize is not available right now.")

    cost = float(prize.get("cost", 0.0) or 0.0)
    if cost <= 0:
        return await p2p_store(request, error="Prize cost is invalid. Contact an administrator.")

    quantity = prize.get("quantity")
    if quantity is not None and quantity <= 0:
        return await p2p_store(request, error="This prize is currently sold out.")

    email_norm = _normalize_email(email)
    balance_before = await _scorepad_balance(email_norm)
    if balance_before < cost - 1e-9:
        return await p2p_store(request, error="Insufficient scorepad balance for this redemption.")

    prize_id_clean = str(prize.get("id", "")).strip()
    if not prize_id_clean:
        return await p2p_store(request, error="Unable to locate that prize. Contact support.")

    prize_key = _p2p_prize_key(prize_id_clean)
    limited_inventory = quantity is not None
    pipe = redis_client.pipeline()
    pipe.hincrbyfloat("score_pad", email_norm, -cost)
    if limited_inventory:
        pipe.hincrby(prize_key, "quantity", -1)
    results = await pipe.execute()

    new_balance_raw = results[0] if results else 0.0
    try:
        new_balance = float(new_balance_raw or 0.0)
    except Exception:
        new_balance = 0.0

    quantity_after: int | None = quantity
    if limited_inventory:
        try:
            quantity_after = int(results[1])
        except Exception:
            quantity_after = quantity

    if new_balance < -1e-6 or (limited_inventory and quantity_after is not None and quantity_after < 0):
        revert = redis_client.pipeline()
        revert.hincrbyfloat("score_pad", email_norm, cost)
        if limited_inventory:
            revert.hincrby(prize_key, "quantity", 1)
        await revert.execute()
        return await p2p_store(
            request,
            error="Your balance changed while redeeming. Please try again.",
        )

    now_iso = datetime.utcnow().isoformat()
    await redis_client.hset(
        prize_key,
        mapping={
            "updated_at": now_iso,
            "last_redeemed_at": now_iso,
            "last_redeemed_by": email_norm,
        },
    )

    try:
        await _load_csv()
    except Exception as exc:
        print(f"[p2p] failed to refresh leaderboard cache after redemption: {exc}")

    await _record_p2p_redemption(email_norm, prize, cost, balance_before, note)

    success_message = f"Redeemed {prize.get('name') or 'prize'} for {cost:.2f} points"
    return RedirectResponse(
        f"/p2p?success={quote_plus(success_message)}",
        status_code=303,
    )


@app.get("/staking")
async def staking_dashboard(
    request: Request,
    success: str | None = None,
    error: str | None = None,
) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    profile = await _ambassador_entry_by_email(email)
    balances = await _stake_balances(email, profile=profile)
    stake_record = await _get_stake(email)
    stake_view = _stake_view(stake_record) if stake_record else None
    success_msg = success or request.query_params.get("success", "")
    error_msg = error or request.query_params.get("error", "")

    return templates.TemplateResponse(
        "staking.html",
        {
            "request": request,
            "profile": profile,
            "available_points": balances["available"],
            "total_points": balances["total"],
            "staked_amount": balances["staked"],
            "scorepad_balance": balances["scorepad"],
            "stake": stake_view,
            "success": success_msg,
            "error": error_msg,
            "stake_duration_days": STAKE_DURATION_DAYS,
        },
    )


@app.post("/staking")
async def staking_submit(request: Request, amount: str = Form(...)) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    try:
        amount_value = float(str(amount).strip())
    except Exception:
        amount_value = -1.0

    if amount_value <= 0:
        return await staking_dashboard(request, error="Enter a positive amount to stake.")

    profile = await _ambassador_entry_by_email(email)
    balances = await _stake_balances(email, profile=profile)

    if balances["staked"] > 0:
        return await staking_dashboard(request, error="You already have an active stake.")

    if balances["available"] <= 0:
        return await staking_dashboard(request, error="No points available to stake.")

    if amount_value > balances["available"]:
        return await staking_dashboard(request, error="Stake amount exceeds your available balance.")

    ok, err = await _create_stake(email, amount_value, created_by="user")
    if not ok:
        return await staking_dashboard(request, error=err or "Unable to create stake right now.")

    success_message = f"Staked {amount_value:.2f} IGP for weekly rewards."
    return RedirectResponse(
        f"/staking?success={quote_plus(success_message)}",
        status_code=303,
    )


@app.post("/staking/unstake")
async def staking_unstake(request: Request) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    ok, err = await _release_stake(email)
    if ok:
        return RedirectResponse(
            f"/staking?success={quote_plus('Stake released back to your balance.')}",
            status_code=303,
        )
    return RedirectResponse(
        f"/staking?error={quote_plus(err or 'Unable to unstake right now.')}",
        status_code=303,
    )


@app.get("/api/transfers/rolodex")
async def api_transfers_rolodex(request: Request, q: str = Query("")) -> JSONResponse:
    email = await _current_email(request)
    if not email:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    search = str(q or "").strip().lower()
    handle_search = search.lstrip("@") if search else ""
    entries = await _leaderboard_entries()
    results: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("email") == email:
            continue
        if entry.get("guardian"):
            continue
        telegram_norm = entry.get("telegram_norm", "")
        telegram_display = str(entry.get("telegram", ""))
        name = str(entry.get("name", ""))
        email_display = entry.get("email_display")

        if search:
            search_hit = False
            if telegram_norm and handle_search and handle_search in telegram_norm:
                search_hit = True
            elif telegram_norm and search in f"@{telegram_norm}":
                search_hit = True
            elif telegram_display and search in telegram_display.lower():
                search_hit = True
            elif search in name.lower():
                search_hit = True
            elif email_display and search in str(email_display).lower():
                search_hit = True
            if not search_hit:
                continue

        email_value = entry.get("email")
        if (not email_value) and telegram_norm:
            email_lookup = await _email_from_telegram(telegram_norm)
            if email_lookup:
                email_value = email_lookup
                email_display = email_display or email_lookup

        identifier = email_value or telegram_display or (f"@{telegram_norm}" if telegram_norm else "")
        if not identifier:
            continue
        results.append(
            {
                "email": email_value,
                "email_display": email_display or email_value,
                "name": name,
                "telegram": telegram_display,
                "points": entry.get("points", 0.0),
                "identifier": identifier,
            }
        )

    results.sort(key=lambda item: float(item.get("points", 0.0)), reverse=True)
    return JSONResponse({"ok": True, "results": results})
    # limit = int(request.query_params.get("limit", 100))
    # page = int(request.query_params.get("page", 1))
    # start = (page - 1) * limit
    # end = start + limit

    # results.sort(key=lambda item: float(item.get("points", 0.0)), reverse=True)
    # return JSONResponse({
    #     "ok": True,
    #     "results": results[start:end],
    #     "total": len(results),
    #     "page": page,
    #     "limit": limit
    # })


@app.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    token = request.cookies.get("session")
    if token:
        await redis_client.delete(f"session:{token}")
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response


@app.get("/tasks")
async def tasks_page(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    statuses = await redis_client.hgetall(f"tasks:{email}")
    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "tasks": TASK_LIST,
            "statuses": statuses,
        },
    )


@app.post("/tasks/apply")
async def tasks_apply(request: Request, task_id: str = Form(...)) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    await redis_client.hset(f"tasks:{email}", task_id, "applied")
    return RedirectResponse("/tasks", status_code=303)


@app.get("/verify")
async def verify_form(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    pending = await redis_client.lrange(f"posts:{email}", 0, -1)
    verified = await redis_client.smembers(f"posts_verified:{email}")
    rejected = await redis_client.smembers(f"posts_rejected:{email}")
    return templates.TemplateResponse(
        "verify.html",
        {
            "request": request,
            "pending": pending,
            "verified": verified,
            "rejected": rejected,
            "error": "",
        },
    )


@app.post("/verify")
async def verify_submit(request: Request, url: str = Form(...)) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    url_clean = url.strip()
    if url_clean:
        pending = await redis_client.lrange(f"posts:{email}", 0, -1)
        verified = await redis_client.smembers(f"posts_verified:{email}")
        if (
            url_clean not in {str(p) for p in pending}
            and url_clean not in {str(v) for v in verified}
        ):
            await redis_client.srem(f"posts_rejected:{email}", url_clean)
            await redis_client.lpush(f"posts:{email}", url_clean)
    return RedirectResponse("/verify", status_code=303)


@app.post("/verify/delete")
async def verify_delete(request: Request, url: str = Form(...)) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    url_clean = url.strip()
    if url_clean:
        await redis_client.lrem(f"posts:{email}", 0, url_clean)
        await redis_client.sadd(f"posts_rejected:{email}", url_clean)
        await redis_client.srem(f"posts_verified:{email}", url_clean)
    return RedirectResponse("/verify", status_code=303)


@app.get("/raid")
async def raid_page(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    entries = await _all_verified_posts()
    return templates.TemplateResponse(
        "raid.html", {"request": request, "entries": entries}
    )


@app.get("/proposals")
async def proposals_page(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    proposals = await _active_proposals(email)
    return templates.TemplateResponse(
        "proposals.html", {"request": request, "proposals": proposals}
    )


@app.post("/proposals/submit")
async def proposals_submit(
    request: Request, title: str = Form(...), content: str = Form(...)
) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    user = await redis_client.hgetall(f"user:{email}")
    pid = await redis_client.incr("proposal_id")
    await redis_client.hset(
        f"proposal:{pid}",
        mapping={
            "title": title.strip(),
            "content": content.strip(),
            "email": email,
            "telegram": user.get("telegram", ""),
            "wallet": user.get("wallet", ""),
            "status": "pending",
        },
    )
    return RedirectResponse("/proposals", status_code=303)


@app.post("/proposals/vote")
async def proposals_vote(
    request: Request, proposal_id: str = Form(...), choice: str = Form(...)
) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    pid = proposal_id.strip()
    yes_key = f"proposal_votes_yes:{pid}"
    no_key = f"proposal_votes_no:{pid}"
    pipe = redis_client.pipeline()
    if choice == "yes":
        pipe.sadd(yes_key, email)
        pipe.srem(no_key, email)
    elif choice == "no":
        pipe.sadd(no_key, email)
        pipe.srem(yes_key, email)
    if pipe.command_stack:
        await pipe.execute()
    return RedirectResponse("/proposals", status_code=303)


@app.get("/admin/login")
async def admin_login_form(request: Request) -> Any:
    return templates.TemplateResponse(
        "admin_login.html", {"request": request, "error": ""}
    )


@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)) -> Any:
    if ADMIN_PASSWORD and password == ADMIN_PASSWORD:
        token = secrets.token_urlsafe(32)
        await redis_client.set(f"admin_session:{token}", "admin", ex=SESSION_TTL_SECONDS)
        response = RedirectResponse("/admin", status_code=303)
        response.set_cookie("admin", token, httponly=True, max_age=SESSION_TTL_SECONDS)
        return response
    return templates.TemplateResponse(
        "admin_login.html", {"request": request, "error": "Invalid password"}
    )


@app.get("/admin/logout")
async def admin_logout(request: Request) -> RedirectResponse:
    token = request.cookies.get("admin")
    if token:
        await redis_client.delete(f"admin_session:{token}")
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("admin")
    return response


@app.get("/admin")
async def admin_panel(request: Request) -> Any:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    # Pagination params
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 20))

    await _ensure_existing_ambassadors_pending()

    wallets = await _all_wallets()
    wallets_active = sorted(
        [w for w in wallets if w.get("active")], key=lambda w: w.get("email", "")
    )
    wallets_inactive = sorted(
        [w for w in wallets if not w.get("active")], key=lambda w: w.get("email", "")
    )
    posts = await _all_posts()
    tasks = await _all_tasks()
    proposals = await _pending_proposals()
    recoveries = await _all_recoveries()
    analytics = await _analytics_dashboard(page=page, limit=limit)
    gamefi_state = await _wheel_state(None, limit=15)
    maintenance_enabled = await _maintenance_enabled()
    # transfers = await _all_transfer_history()
    pending_referrals = await _pending_referrals()
    stakes = await _all_active_stakes()
    stakes_total = sum(float(entry.get("amount", 0.0) or 0.0) for entry in stakes)
    stakes_message = request.query_params.get("stakes_msg", "")
    stakes_error = request.query_params.get("stakes_err", "")
    kyc_records = await _all_kyc_records()
    kyc_counts = {
        "pending": sum(1 for record in kyc_records if record.get("status") == KYC_STATUS_PENDING),
        "verified": sum(1 for record in kyc_records if record.get("status") == KYC_STATUS_VERIFIED),
        "rejected": sum(1 for record in kyc_records if record.get("status") == KYC_STATUS_REJECTED),
    }
    kyc_message = request.query_params.get("kyc_msg", "")
    kyc_error = request.query_params.get("kyc_err", "")
    p2p_prizes = await _p2p_prizes(include_inactive=True)
    p2p_history = await _p2p_recent_history(limit=100)
    p2p_message = request.query_params.get("p2p_msg", "")
    p2p_error = request.query_params.get("p2p_err", "")
    gamefi_message = request.query_params.get("gamefi_msg", "")
    gamefi_error = request.query_params.get("gamefi_err", "")
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "wallets": wallets,
            "wallets_active": wallets_active,
            "wallets_inactive": wallets_inactive,
            "posts": posts,
            "tasks": tasks,
            "recoveries": recoveries,
            "task_labels": TASK_LABELS,
            "proposals": proposals,
            "analytics": analytics,
            "maintenance_enabled": maintenance_enabled,
            "gamefi_state": gamefi_state,
            "gamefi_message": gamefi_message,
            "gamefi_error": gamefi_error,
            # "transfers": transfers,
            "verified_search_limit": VERIFIED_SEARCH_LIMIT,
            "pending_referrals": pending_referrals,
            "stakes": stakes,
            "stakes_total": stakes_total,
            "stakes_message": stakes_message,
            "stakes_error": stakes_error,
            "stake_duration_days": STAKE_DURATION_DAYS,
            "kyc_records": kyc_records,
            "kyc_counts": kyc_counts,
            "kyc_message": kyc_message,
            "kyc_error": kyc_error,
            "p2p_prizes": p2p_prizes,
            "p2p_history": p2p_history,
            "p2p_message": p2p_message,
            "p2p_error": p2p_error,
        },
    )


@app.post("/admin/gamefi/wheel")
async def admin_gamefi_wheel_update(request: Request) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    form = await request.form()
    config = await _ensure_wheel_config()

    entry_fee = config["entry_fee"]
    entry_fee_raw = form.get("entry_fee")
    if entry_fee_raw is not None and str(entry_fee_raw).strip() != "":
        try:
            entry_fee = float(str(entry_fee_raw).replace(",", "").strip())
        except Exception:
            err = quote_plus("Entry fee must be a valid number.")
            return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
    if entry_fee < 0:
        err = quote_plus("Entry fee cannot be negative.")
        return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)

    pool_balance = config["pool_balance"]
    pool_adjust_raw = form.get("pool_adjust")
    pool_adjust_amount = 0.0
    if pool_adjust_raw is not None and str(pool_adjust_raw).strip() != "":
        try:
            pool_adjust_amount = float(str(pool_adjust_raw).replace(",", "").strip())
        except Exception:
            err = quote_plus("Pool adjustment must be a valid number.")
            return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
        new_balance = pool_balance + pool_adjust_amount
        if new_balance < 0:
            err = quote_plus("Pool balance cannot drop below zero.")
            return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
        pool_balance = new_balance
    else:
        pool_balance_raw = form.get("pool_balance")
        if pool_balance_raw is not None and str(pool_balance_raw).strip() != "":
            try:
                pool_balance = float(str(pool_balance_raw).replace(",", "").strip())
            except Exception:
                err = quote_plus("Pool balance must be a valid number.")
                return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
            if pool_balance < 0:
                err = quote_plus("Pool balance cannot be negative.")
                return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)

    cooldown_seconds = config["cooldown_seconds"]
    cooldown_raw = form.get("cooldown_seconds")
    if cooldown_raw is not None and str(cooldown_raw).strip() != "":
        try:
            cooldown_seconds = int(float(str(cooldown_raw).replace(",", "").strip()))
        except Exception:
            err = quote_plus("Cooldown must be a whole number of seconds.")
            return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
    if cooldown_seconds < 0:
        err = quote_plus("Cooldown cannot be negative.")
        return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)

    enabled_value = str(form.get("enabled", "")).strip().lower()
    enabled = enabled_value not in {"", "0", "false", "off"}

    status_message = _safe_text(form.get("status_message", "")).strip()
    if len(status_message) > 240:
        status_message = status_message[:240]
    status_tone_raw = str(form.get("status_tone", "neutral") or "neutral").strip().lower()
    status_tone = (
        status_tone_raw if status_tone_raw in {"neutral", "win", "lose", "bonus"} else "neutral"
    )

    segment_rows: dict[int, dict[str, Any]] = {}
    for key, value in form.multi_items():
        match = WHEEL_SEGMENT_FIELD_RE.fullmatch(key)
        if not match:
            continue
        idx = int(match.group(1))
        field = match.group(2)
        segment_rows.setdefault(idx, {})[field] = value

    segments: list[dict[str, Any]] = []
    for _, row in sorted(segment_rows.items(), key=lambda item: item[0]):
        has_values = any(str(row.get(field, "")).strip() for field in ("label", "id", "type", "weight", "multiplier", "amount"))
        if not has_values:
            continue
        label_raw = _safe_text(row.get("label", ""))
        seg_label = label_raw.strip() or f"Slice {len(segments) + 1}"
        seg_id_raw = _safe_text(row.get("id", ""))
        seg_id = seg_id_raw.strip() or f"segment_{len(segments)}"
        seg_type_raw = str(row.get("type", "") or "").strip().lower()
        seg_type = (
            seg_type_raw
            if seg_type_raw in {"fixed", "multiplier", "bonus", "retry", "lose"}
            else "fixed"
        )
        seg_tone_raw = str(row.get("tone", "") or "").strip().lower()
        seg_tone = (
            seg_tone_raw if seg_tone_raw in {"neutral", "win", "lose", "bonus"} else "neutral"
        )
        weight_raw = str(row.get("weight", "")).strip()
        if weight_raw:
            try:
                seg_weight = float(weight_raw.replace(",", ""))
            except Exception:
                err = quote_plus(f"Weight for slice '{seg_label}' must be numeric.")
                return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
        else:
            seg_weight = 0.0
        seg_weight = max(0.0, seg_weight)

        index_raw = str(row.get("index", "")).strip()
        if index_raw:
            try:
                seg_index = int(float(index_raw.replace(",", "")))
            except Exception:
                err = quote_plus(f"Index for slice '{seg_label}' must be numeric.")
                return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
            seg_index = max(0, seg_index)
        else:
            seg_index = len(segments)

        segment_entry: dict[str, Any] = {
            "id": seg_id,
            "label": seg_label,
            "type": seg_type,
            "tone": seg_tone,
            "weight": seg_weight,
            "index": seg_index,
        }

        if seg_type == "multiplier":
            multiplier_raw = str(row.get("multiplier", "")).strip()
            if multiplier_raw:
                try:
                    multiplier_value = float(multiplier_raw.replace(",", ""))
                except Exception:
                    err = quote_plus(f"Multiplier for slice '{seg_label}' must be numeric.")
                    return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
            else:
                multiplier_value = 0.0
            segment_entry["multiplier"] = max(0.0, multiplier_value)
        elif seg_type == "fixed":
            amount_raw = str(row.get("amount", "")).strip()
            if amount_raw:
                try:
                    amount_value = float(amount_raw.replace(",", ""))
                except Exception:
                    err = quote_plus(f"Amount for slice '{seg_label}' must be numeric.")
                    return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)
            else:
                amount_value = 0.0
            segment_entry["amount"] = max(0.0, amount_value)

        segments.append(segment_entry)

    if not segments:
        err = quote_plus("Configure at least one wheel slice before saving.")
        return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)

    segments_sorted = sorted(segments, key=lambda seg: seg.get("index", 0))
    for idx, segment in enumerate(segments_sorted):
        segment["index"] = idx

    now_iso = datetime.utcnow().isoformat()
    payload = {
        "entry_fee": f"{max(0.0, entry_fee):.6f}",
        "pool_balance": f"{max(0.0, pool_balance):.6f}",
        "cooldown_seconds": str(max(0, cooldown_seconds)),
        "enabled": "1" if enabled else "0",
        "segments": json.dumps(segments_sorted),
        "status_message": status_message,
        "status_tone": status_tone,
        "updated_at": now_iso,
    }

    global_lock = redis_client.lock(WHEEL_LOCK_KEY, timeout=8, blocking_timeout=4)
    try:
        try:
            acquired = await global_lock.acquire(blocking=True)
        except LockError:
            acquired = False
        if not acquired:
            err = quote_plus("Wheel is busy. Please try again.")
            return RedirectResponse(f"/admin?gamefi_err={err}#gamefi", status_code=303)

        await redis_client.hset(WHEEL_CONFIG_KEY, mapping=payload)
    finally:
        try:
            await global_lock.release()
        except LockError:
            pass

    if pool_adjust_amount:
        direction = "increased" if pool_adjust_amount > 0 else "decreased"
        msg = (
            f"Wheel updated. Pool {direction} by {abs(pool_adjust_amount):.0f} IGP "
            f"(now {max(0.0, pool_balance):.0f})."
        )
    else:
        msg = "Wheel configuration updated."
    message = quote_plus(msg)
    return RedirectResponse(f"/admin?gamefi_msg={message}#gamefi", status_code=303)


@app.post("/admin/p2p/prizes")
async def admin_p2p_create(
    request: Request,
    name: str = Form(...),
    cost: str = Form(...),
    quantity: str = Form(""),
    description: str = Form(""),
    active: str = Form("1"),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    name_clean = _safe_text(name).strip()
    if not name_clean:
        message = quote_plus("Prize name is required.")
        return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    try:
        cost_value = float(str(cost).strip())
    except Exception:
        cost_value = -1.0
    if cost_value <= 0:
        message = quote_plus("Enter a positive cost for the prize.")
        return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    quantity_value: int | None = None
    quantity_raw = str(quantity or "").strip()
    if quantity_raw:
        try:
            quantity_value = int(quantity_raw)
        except Exception:
            message = quote_plus("Quantity must be a whole number or left blank for unlimited stock.")
            return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)
        if quantity_value < 0:
            message = quote_plus("Quantity cannot be negative.")
            return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    description_clean = _safe_text(description)[:500]
    active_flag = _p2p_parse_bool(active)

    new_id = await redis_client.incr(P2P_PRIZE_SEQ_KEY)
    prize_id = str(new_id)
    now_iso = datetime.utcnow().isoformat()
    mapping: dict[str, Any] = {
        "id": prize_id,
        "name": name_clean,
        "description": description_clean,
        "cost": f"{cost_value:.2f}",
        "active": "1" if active_flag else "0",
        "created_at": now_iso,
        "updated_at": now_iso,
        "created_by": "admin",
    }
    mapping["quantity"] = str(quantity_value) if quantity_value is not None else ""

    pipe = redis_client.pipeline()
    pipe.hset(_p2p_prize_key(prize_id), mapping=mapping)
    pipe.zadd(P2P_PRIZE_INDEX_KEY, {prize_id: datetime.utcnow().timestamp()})
    await pipe.execute()

    message = quote_plus("Prize added to the P2P shop.")
    return RedirectResponse(f"/admin?p2p_msg={message}#p2p", status_code=303)


@app.post("/admin/p2p/prizes/update")
async def admin_p2p_update(
    request: Request,
    prize_id: str = Form(...),
    name: str = Form(...),
    cost: str = Form(...),
    quantity: str = Form(""),
    description: str = Form(""),
    active: str = Form("0"),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    prize = await _p2p_prize(prize_id)
    if not prize:
        message = quote_plus("Prize not found.")
        return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    name_clean = _safe_text(name).strip()
    if not name_clean:
        message = quote_plus("Prize name cannot be empty.")
        return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    try:
        cost_value = float(str(cost).strip())
    except Exception:
        cost_value = -1.0
    if cost_value <= 0:
        message = quote_plus("Enter a positive cost for the prize.")
        return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    quantity_value: int | None = None
    quantity_raw = str(quantity or "").strip()
    if quantity_raw:
        try:
            quantity_value = int(quantity_raw)
        except Exception:
            message = quote_plus("Quantity must be a whole number or left blank for unlimited stock.")
            return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)
        if quantity_value < 0:
            message = quote_plus("Quantity cannot be negative.")
            return RedirectResponse(f"/admin?p2p_err={message}#p2p", status_code=303)

    description_clean = _safe_text(description)[:500]
    active_flag = _p2p_parse_bool(active)
    now_iso = datetime.utcnow().isoformat()
    mapping: dict[str, Any] = {
        "name": name_clean,
        "description": description_clean,
        "cost": f"{cost_value:.2f}",
        "active": "1" if active_flag else "0",
        "updated_at": now_iso,
    }
    mapping["quantity"] = str(quantity_value) if quantity_value is not None else ""

    await redis_client.hset(_p2p_prize_key(prize.get("id") or prize_id), mapping=mapping)

    message = quote_plus("Prize updated successfully.")
    return RedirectResponse(f"/admin?p2p_msg={message}#p2p", status_code=303)


@app.post("/admin/p2p/prizes/delete")
async def admin_p2p_delete(
    request: Request,
    prize_id: str = Form(...),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    await _p2p_delete_prize(prize_id)

    message = quote_plus("Prize removed from the P2P shop.")
    return RedirectResponse(f"/admin?p2p_msg={message}#p2p", status_code=303)


async def _approve_pending_applicant(email: str) -> bool:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return False

    key = f"user:{email_norm}"
    data = await redis_client.hgetall(key)
    if not data:
        return False

    await redis_client.hset(
        key,
        mapping={
            "verified": 1,
            "verified_at": datetime.utcnow().isoformat(),
        },
    )

    telegram = str(data.get("telegram", ""))
    try:
        _ensure_leaderboard_entry(email_norm, telegram)
    except Exception as exc:
        print(f"[admin] failed to update leaderboard for {email_norm}: {exc}")

    _register_email_record(email_norm)

    referrer = str(data.get("referred_by", "")).strip().lower()
    if referrer:
        await _set_referral_status(referrer, email_norm, "approved")

    return True


async def _reject_pending_applicant(email: str) -> bool:
    """Mark a pending applicant as rejected without deleting their record."""

    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return False

    # ✅ Remove from leaderboard (optional — you might still want this)
    # removed_from_leaderboard = _remove_leaderboard_entry(email_norm)

    key = f"user:{email_norm}"
    data = await redis_client.hgetall(key)
    if data:
        referrer = str(data.get("referred_by", "")).strip().lower()
        if referrer:
            # ✅ Only update referral status — don't delete anything
            await _set_referral_status(referrer, email_norm, "rejected")

        # ✅ Mark the user as rejected instead of deleting them
        await redis_client.hset(
            key,
            mapping={
                "verified": 0,
                "rejected": 1,
                "rejected_at": datetime.utcnow().isoformat(),
            },
        )

        # 🚨 DO NOT DELETE user data, tasks, transfers, etc.
        # Leave these for audit trails or potential reinstatement later.

    # ✅ Optional: still remove them from CSV records if you want
    # _unregister_email_record(email_norm)

    return True


@app.post("/admin/referrals/approve")
async def admin_referral_approve(
    request: Request,
    email: str = Form(""),
    emails: list[str] | None = Form(None),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    targets: set[str] = set()

    if email:
        targets.add(str(email).strip().lower())

    if emails:
        for value in emails:
            value_norm = str(value or "").strip().lower()
            if value_norm:
                targets.add(value_norm)

    if not targets:
        return RedirectResponse("/admin#referrals", status_code=303)

    refresh_needed = False
    for target in targets:
        processed = await _approve_pending_applicant(target)
        refresh_needed = refresh_needed or processed

    if refresh_needed:
        try:
            await _get_cached_data(force_refresh=True)
        except Exception as exc:
            print(f"[admin] failed to refresh leaderboard cache: {exc}")

    return RedirectResponse("/admin#referrals", status_code=303)


@app.post("/admin/referrals/reject")
async def admin_referral_reject(
    request: Request,
    email: str = Form(""),
    emails: list[str] | None = Form(None),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    targets: set[str] = set()

    if email:
        targets.add(str(email).strip().lower())

    if emails:
        for value in emails:
            value_norm = str(value or "").strip().lower()
            if value_norm:
                targets.add(value_norm)

    if not targets:
        return RedirectResponse("/admin#referrals", status_code=303)

    refresh_needed = False
    for target in targets:
        removed = await _reject_pending_applicant(target)
        refresh_needed = refresh_needed or removed

    if refresh_needed:
        try:
            await _get_cached_data(force_refresh=True)
        except Exception as exc:
            print(f"[admin] failed to refresh leaderboard cache: {exc}")

    return RedirectResponse("/admin#referrals", status_code=303)


@app.post("/admin/stakes/unstake")
async def admin_stakes_unstake(
    request: Request, emails: str = Form(""), ghost: str = Form("")
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin?stakes_err=Invalid+ghost+key#stakes", status_code=303)

    raw = str(emails or "").strip()
    if not raw:
        return RedirectResponse("/admin?stakes_err=Provide+one+or+more+emails#stakes", status_code=303)

    candidates: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\n,]", raw):
        value_norm = _normalize_email(part)
        if value_norm and value_norm not in seen:
            seen.add(value_norm)
            candidates.append(value_norm)

    if not candidates:
        return RedirectResponse("/admin?stakes_err=No+valid+emails+found#stakes", status_code=303)

    successes = 0
    failures: list[str] = []
    for candidate in candidates:
        ok, err = await _release_stake(candidate)
        if ok:
            successes += 1
        else:
            failures.append(f"{candidate}: {err or 'unable to unstake'}")

    params: list[tuple[str, str]] = []
    if successes:
        label = "stake" if successes == 1 else "stakes"
        params.append(("stakes_msg", f"Unstaked {successes} {label}."))
    if failures:
        joined = "; ".join(failures[:5])
        params.append(("stakes_err", joined))

    query = "&".join(f"{key}={quote_plus(value)}" for key, value in params if value)
    redirect_url = "/admin#stakes"
    if query:
        redirect_url = f"/admin?{query}#stakes"
    return RedirectResponse(redirect_url, status_code=303)


@app.post("/admin/maintenance")
async def admin_maintenance_toggle(
    request: Request, enabled: str = Form(...)
) -> RedirectResponse:
    
    if not await _current_admin(request):
        return RedirectResponse("/admin/login", status_code=303)

    is_enabled = str(enabled).strip().lower() in {"1", "true", "yes", "on"}
    await _set_maintenance(is_enabled)

    return RedirectResponse("/admin", status_code=303)
    # Require Ghost key (same pattern as scorepad/posts/tasks forms)
    # if not ghost or ghost != os.getenv("ADMIN_GHOST_KEY"):
    #     raise HTTPException(status_code=403, detail="Invalid ghost key")


@app.post("/admin/recovery/reset")
async def admin_recovery_reset(
    request: Request, email: str = Form(...), ghost: str = Form("")
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)
    email_norm = email.strip().lower()
    key = f"recovery:{email_norm}"
    raw = await redis_client.get(key)
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
        if data and data.get("code"):
            code = data["code"]
            await redis_client.hset(
                f"user:{email_norm}", mapping={"password": _hash_password(code)}
            )
            await redis_client.delete(key)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/activity/reset")
async def admin_activity_reset(request: Request, ghost: str = Form("")) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)

    await redis_client.set(ACTIVITY_RESET_KEY, _monday_start(datetime.utcnow()).isoformat())

    activity_keys = [
        key async for key in redis_client.scan_iter(f"{ACTIVITY_ZSET_PREFIX}*")
    ]
    if activity_keys:
        await redis_client.delete(*activity_keys)

    pipe = redis_client.pipeline()
    async for user_key in redis_client.scan_iter("user:*"):
        pipe.hset(user_key, "activity", "inactive")
    if pipe.command_stack:
        await pipe.execute()

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/transfers/reset")
async def admin_transfers_reset(request: Request, ghost: str = Form("")) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)

    await _zero_transfer_history()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/transfers/delete")
async def admin_transfers_delete(request: Request, ghost: str = Form("")) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)

    await _delete_transfer_history()
    return RedirectResponse("/admin", status_code=303)


@app.get("/api/admin/wallets")
async def api_admin_wallets(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    wallets = await _all_wallets()
    return JSONResponse({"ok": True, "wallets": wallets})


@app.get("/api/admin/validate_wallets")
async def api_admin_validate_wallets(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    if not _daemon_ready():
        return JSONResponse({"ok": False, "error": "daemon_unavailable"}, status_code=503)
    wallets = await _all_wallets()
    bad: list[dict[str, str]] = []
    for w in wallets:
        addr = w.get("wallet") or ""
        email = w.get("email", "")
        tele = w.get("telegram", "")
        if not addr:
            bad.append({"email": email, "telegram": tele, "wallet": addr})
            continue
        try:
            cp = _run_cli("validateaddress", addr)
            data = json.loads(cp.stdout or "{}")
            if not data.get("isvalid", False):
                bad.append({"email": email, "telegram": tele, "wallet": addr})
        except Exception:
            bad.append({"email": email, "telegram": tele, "wallet": addr})
    return JSONResponse({"ok": True, "invalid": bad})


@app.get("/api/admin/export")
async def api_admin_export(
    request: Request, fmt: str = Query("json"), ghost: str = Query("")
) -> Response:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    wallets = await _all_wallets()
    export_rows = [
        {
            "email": w.get("email", ""),
            "wallet": w.get("wallet", ""),
            "telegram": w.get("telegram", ""),
            "points": w.get("points", 0.0),
            "pending_reward": float(w.get("pending_reward", 0.0)),
            "verified": bool(w.get("verified", False)),
            "posts": int(w.get("verified_posts", 0)),
            "activity": str(w.get("activity", "inactive")),
        }
        for w in wallets
    ]
    if fmt.lower() == "csv":
        output = io.StringIO()
        fieldnames = [
            "email",
            "wallet",
            "telegram",
            "points",
            "pending_reward",
            "verified",
            "posts",
            "activity",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_rows)
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ambassadors.csv"},
        )
    return JSONResponse({"ok": True, "ambassadors": export_rows})


@app.get("/api/admin/posts")
async def api_admin_posts(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    posts = await _all_posts()
    return JSONResponse({"ok": True, "posts": posts})


@app.get("/api/admin/posts/search")
async def api_admin_posts_search(request: Request, q: str = Query("")) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    query = str(q or "").strip()
    if not query:
        return JSONResponse({"ok": True, "results": [], "count": 0, "limit": VERIFIED_SEARCH_LIMIT})

    entries = await _all_verified_posts(include_email=True)
    if not entries:
        return JSONResponse({"ok": True, "results": [], "count": 0, "limit": VERIFIED_SEARCH_LIMIT})

    wallet_lookup: dict[str, dict[str, Any]] = {}
    for wallet in await _all_wallets():
        email = str(wallet.get("email", "")).strip().lower()
        if email and email not in wallet_lookup:
            wallet_lookup[email] = wallet

    query_lower = query.lower()
    results: list[dict[str, Any]] = []
    total_matches = 0

    for entry in entries:
        url = entry.get("url", "")
        if not url:
            continue
        if query_lower in url.lower():
            total_matches += 1
            if len(results) >= VERIFIED_SEARCH_LIMIT:
                continue

            email = entry.get("email", "")
            telegram = entry.get("telegram", "")
            tg_link = entry.get("tg_link", "")
            wallet = entry.get("wallet", "")

            result: dict[str, Any] = {
                "url": url,
                "email": email,
                "telegram": telegram,
                "tg_link": tg_link,
                "wallet": wallet,
            }

            wallet_info = wallet_lookup.get(email)
            if wallet_info:
                result["card"] = {
                    "wallet": wallet_info.get("wallet", ""),
                    "telegram": wallet_info.get("telegram", ""),
                    "tg_link": wallet_info.get("tg_link", ""),
                    "pad": wallet_info.get("pad", 0.0),
                    "pending_reward": wallet_info.get("pending_reward", ""),
                    "points": wallet_info.get("points", 0.0),
                    "verified": bool(wallet_info.get("verified")),
                    "active": bool(wallet_info.get("active")),
                    "guardian": bool(wallet_info.get("guardian")),
                }
            results.append(result)

    return JSONResponse(
        {
            "ok": True,
            "results": results,
            "count": total_matches,
            "limit": VERIFIED_SEARCH_LIMIT,
        }
    )


@app.post("/admin/posts/verify")
async def admin_post_verify(
    request: Request,
    selected: list[str] = Form([]),
    email: str | None = Form(None),
    url: str | None = Form(None),
    verify_all: str | None = Form(None),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    def _clean_url(v) -> str:
        # force plain UTF-8 string without surrogates/odd bytes
        return str(v).strip().encode("utf-8", "ignore").decode("utf-8", "ignore")

    pipe = redis_client.pipeline()
    touched_emails: set[str] = set()

    if verify_all:
        # Works with BOTH shapes:
        #   { email: [ {"url": "...", "verified": bool}, ... ] }
        #   { email: [ "https://...", ... ] }
        posts = await _all_posts()
        for eml, entries in posts.items():
            eml_key = eml.strip().lower()
            if eml_key:
                touched_emails.add(eml_key)
            for entry in entries:
                if isinstance(entry, dict):
                    u = entry.get("url", "")
                else:
                    u = entry
                u = _clean_url(u)
                if u:
                    pipe.sadd(f"posts_verified:{eml_key}", u)
                    pipe.srem(f"posts_rejected:{eml_key}", u)
                    pipe.lrem(f"posts:{eml_key}", 0, u)
                    pipe.zadd(
                        f"{ACTIVITY_ZSET_PREFIX}{eml_key}",
                        {u: datetime.utcnow().timestamp()},
                    )

    else:
        # Selected checkboxes and/or single email+url
        items = list(selected)
        if email and url:
            items.append(f"{email.strip().lower()}||{url.strip()}")

        for item in items:
            if not item or "||" not in item:
                continue
            eml, u = item.split("||", 1)
            eml_key = eml.strip().lower()
            u = _clean_url(u)
            if eml_key and u:
                pipe.sadd(f"posts_verified:{eml_key}", u)
                touched_emails.add(eml_key)
                pipe.srem(f"posts_rejected:{eml_key}", u)
                pipe.lrem(f"posts:{eml_key}", 0, u)
                pipe.zadd(
                    f"{ACTIVITY_ZSET_PREFIX}{eml_key}",
                    {u: datetime.utcnow().timestamp()},
                )

    if pipe.command_stack:
        await pipe.execute()
        for eml in touched_emails:
            await redis_client.hset(
                f"user:{eml}", mapping={"verified": 1, "activity": "active"}
            )

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/posts/reject")
async def admin_post_reject(
    request: Request, email: str = Form(...), url: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    email_key = email.strip().lower()
    url_clean = str(url).strip()
    await redis_client.lrem(f"posts:{email_key}", 0, url_clean)
    await redis_client.srem(f"posts_verified:{email_key}", url_clean)
    await redis_client.sadd(f"posts_rejected:{email_key}", url_clean)
    await redis_client.zrem(f"{ACTIVITY_ZSET_PREFIX}{email_key}", url_clean)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/posts/reject-selected")
async def admin_post_reject_selected(
    request: Request,
    selected: list[str] = Form([]),
    email: str | None = Form(None),
    url: str | None = Form(None),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    items = list(selected)
    if email and url:
        items.append(f"{email.strip().lower()}||{url.strip()}")

    pipe = redis_client.pipeline()

    for item in items:
        if not item or "||" not in item:
            continue
        eml, raw_url = item.split("||", 1)
        email_key = eml.strip().lower()
        url_clean = str(raw_url).strip()
        if not email_key or not url_clean:
            continue
        pipe.lrem(f"posts:{email_key}", 0, url_clean)
        pipe.srem(f"posts_verified:{email_key}", url_clean)
        pipe.sadd(f"posts_rejected:{email_key}", url_clean)
        pipe.zrem(f"{ACTIVITY_ZSET_PREFIX}{email_key}", url_clean)

    if pipe.command_stack:
        await pipe.execute()

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/kyc/verify")
async def admin_kyc_verify(
    request: Request,
    email: str = Form(...),
    notes: str = Form(""),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return RedirectResponse("/admin?kyc_err=Missing+email", status_code=303)
    key = f"kyc:{email_norm}"
    if not await redis_client.exists(key):
        err = quote_plus("No KYC submission found for this user")
        return RedirectResponse(f"/admin?kyc_err={err}#kyc", status_code=303)
    now_iso = datetime.utcnow().isoformat()
    notes_clean = _safe_text(notes).strip()
    await redis_client.hset(
        key,
        mapping={
            "status": KYC_STATUS_VERIFIED,
            "reviewed_at": now_iso,
            "reviewed_by": "admin",
            "rejection_reason": "",
            "admin_notes": notes_clean,
        },
    )
    await _set_user_kyc_status(email_norm, KYC_STATUS_VERIFIED)
    msg = quote_plus("KYC verified")
    return RedirectResponse(f"/admin?kyc_msg={msg}#kyc", status_code=303)


@app.post("/admin/kyc/reject")
async def admin_kyc_reject(
    request: Request,
    email: str = Form(...),
    reason: str = Form(""),
    notes: str = Form(""),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return RedirectResponse("/admin?kyc_err=Missing+email", status_code=303)
    key = f"kyc:{email_norm}"
    if not await redis_client.exists(key):
        err = quote_plus("No KYC submission found for this user")
        return RedirectResponse(f"/admin?kyc_err={err}#kyc", status_code=303)
    now_iso = datetime.utcnow().isoformat()
    reason_clean = _safe_text(reason).strip()
    notes_clean = _safe_text(notes).strip()
    await redis_client.hset(
        key,
        mapping={
            "status": KYC_STATUS_REJECTED,
            "reviewed_at": now_iso,
            "reviewed_by": "admin",
            "rejection_reason": reason_clean,
            "admin_notes": notes_clean,
        },
    )
    await _set_user_kyc_status(email_norm, KYC_STATUS_REJECTED)
    msg = quote_plus("KYC rejected")
    return RedirectResponse(f"/admin?kyc_msg={msg}#kyc", status_code=303)


@app.post("/admin/proposals/verify")
async def admin_proposal_verify(
    request: Request,
    proposal_id: str = Form(...),
    funding_wallet: str = Form("")
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    mapping = {"status": "active"}
    fw = funding_wallet.strip()
    if fw:
        mapping["funding_wallet"] = fw
    await redis_client.hset(f"proposal:{proposal_id.strip()}", mapping=mapping)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/proposals/reject")
async def admin_proposal_reject(
    request: Request, proposal_id: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    await redis_client.hset(f"proposal:{proposal_id.strip()}", "status", "rejected")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/telegram/update")
async def admin_telegram_update(
    request: Request, email: str = Form(...), telegram: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    await redis_client.hset(
        f"user:{email}", "telegram", _normalize_telegram(telegram)
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/email/update")
async def admin_email_update(
    request: Request,
    current_email: str = Form(...),
    new_email: str = Form(...),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    old_norm = str(current_email or "").strip().lower()
    new_norm = str(new_email or "").strip().lower()
    if not old_norm or not new_norm or old_norm == new_norm:
        return RedirectResponse("/admin", status_code=303)

    await _move_key(f"user:{old_norm}", f"user:{new_norm}")
    await _move_key(f"posts:{old_norm}", f"posts:{new_norm}")
    await _move_key(f"posts_verified:{old_norm}", f"posts_verified:{new_norm}")
    await _move_key(f"posts_rejected:{old_norm}", f"posts_rejected:{new_norm}")
    await _move_key(f"tasks:{old_norm}", f"tasks:{new_norm}")
    await _move_key(f"{ACTIVITY_ZSET_PREFIX}{old_norm}", f"{ACTIVITY_ZSET_PREFIX}{new_norm}")
    await _move_key(f"transfers:{old_norm}", f"transfers:{new_norm}")
    await _move_key(f"recovery:{old_norm}", f"recovery:{new_norm}")

    pad_value = await redis_client.hget("score_pad", old_norm)
    if pad_value is not None:
        await redis_client.hset("score_pad", new_norm, pad_value)
        await redis_client.hdel("score_pad", old_norm)

    if await redis_client.sismember(GUARDIAN_SET_KEY, old_norm):
        await redis_client.srem(GUARDIAN_SET_KEY, old_norm)
        await redis_client.sadd(GUARDIAN_SET_KEY, new_norm)

    REGISTERED_EMAILS.discard(old_norm)
    REGISTERED_EMAILS.add(new_norm)
    
    return RedirectResponse("/admin", status_code=303)
    

@app.post("/admin/scorepad")
async def admin_scorepad(
    request: Request, email: str = Form(...), pad: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    email_key = email.strip().lower()
    try:
        pad_val = float(pad)
    except Exception:
        pad_val = 0.0
    await redis_client.hset("score_pad", email_key, pad_val)
    # Refresh cached leaderboard so padding is reflected immediately
    await _load_csv()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/guardians/toggle")
async def admin_guardian_toggle(
    request: Request,
    email: str = Form(...),
    enable: str = Form("1"),
    ghost: str = Form(""),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)

    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return RedirectResponse("/admin", status_code=303)
    if email_norm not in REGISTERED_EMAILS:
        return RedirectResponse("/admin", status_code=303)

    enable_flag = str(enable).strip().lower() in {"1", "true", "yes", "on"}
    await _set_guardian_status(email_norm, enable_flag)

    try:
        await _load_csv()
    except Exception as exc:
        print(f"[guardian] failed to refresh leaderboard cache: {exc}")

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/scorepad/boost")
async def admin_scorepad_boost(
    request: Request, ghost: str = Form("")
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)

    wallets = await _all_wallets()
    pipe = redis_client.pipeline()
    for wallet in wallets:
        email = str(wallet.get("email", "")).strip().lower()
        if not email or not wallet.get("active"):
            continue
        pipe.hincrbyfloat("score_pad", email, SCOREPAD_BOOST_POINTS)

    if pipe.command_stack:
        await pipe.execute()
        await _load_csv()

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/scorepad/slash")
async def admin_scorepad_slash(
    request: Request, ghost: str = Form("")
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)

    wallets = await _all_wallets()
    pipe = redis_client.pipeline()
    for wallet in wallets:
        email = str(wallet.get("email", "")).strip().lower()
        if not email or wallet.get("active"):
            continue
        pipe.hset("score_pad", email, 0.0)

    if pipe.command_stack:
        await pipe.execute()
        await _load_csv()

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/scorepad/reset")
async def admin_scorepad_reset(
    request: Request,
    emails: list[str] = Form([]),
    reset_all: str | None = Form(None),
    ghost: str = Form(""),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return RedirectResponse("/admin", status_code=303)
    if reset_all:
        await redis_client.delete("score_pad")
    else:
        pipe = redis_client.pipeline()
        for em in emails:
            pipe.hdel("score_pad", em.strip().lower())
        if pipe.command_stack:
            await pipe.execute()
    # Refresh cached leaderboard so padding is reflected immediately
    await _load_csv()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/tasks/bulk")
async def admin_task_bulk(
    request: Request,
    action: str = Form(...),
    selected: list[str] = Form([]),
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")

    action_name = (action or "").strip().lower()

    if action_name == "verify_all":
        tasks = await _all_tasks()
        pipe = redis_client.pipeline()
        touched: set[str] = set()
        for email, mapping in tasks.items():
            email_key = email.strip().lower()
            if not email_key or not mapping:
                continue
            touched.add(email_key)
            for task_id in mapping.keys():
                tid = str(task_id).strip()
                if tid:
                    pipe.hset(f"tasks:{email_key}", tid, "verified")
        if pipe.command_stack:
            await pipe.execute()
            for email_key in touched:
                await redis_client.hset(f"user:{email_key}", "verified", 1)

    elif action_name in {"verify_selected", "destroy_selected"}:
        items: set[tuple[str, str]] = set()
        for raw in selected:
            if not raw or "||" not in raw:
                continue
            email_part, task_part = raw.split("||", 1)
            email_key = email_part.strip().lower()
            task_id = task_part.strip()
            if email_key and task_id:
                items.add((email_key, task_id))

        if items:
            pipe = redis_client.pipeline()
            touched: set[str] = set()
            if action_name == "verify_selected":
                for email_key, task_id in items:
                    pipe.hset(f"tasks:{email_key}", task_id, "verified")
                    touched.add(email_key)
            else:
                for email_key, task_id in items:
                    pipe.hdel(f"tasks:{email_key}", task_id)

            if pipe.command_stack:
                await pipe.execute()
                for email_key in touched:
                    await redis_client.hset(f"user:{email_key}", "verified", 1)

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/tasks/verify")
async def admin_task_verify(
    request: Request, email: str = Form(...), task_id: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    await redis_client.hset(f"tasks:{email}", task_id, "verified")
    await redis_client.hset(f"user:{email}", "verified", 1)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/tasks/destroy")
async def admin_task_destroy(
    request: Request, email: str = Form(...), task_id: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    await redis_client.hdel(f"tasks:{email}", task_id)
    return RedirectResponse("/admin", status_code=303)


@app.get("/api/admin/tasks")
async def api_admin_tasks(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    tasks = await _all_tasks()
    return JSONResponse({"ok": True, "tasks": tasks})


@app.get("/")
async def index(request: Request) -> Any:
    guard = await _maintenance_guard(request)
    if guard:
        return guard
    is_admin = await _current_admin(request)
    if await _maintenance_enabled() and not is_admin:
        return templates.TemplateResponse(
            "maintenance.html",
            {"request": request},
            status_code=503,
        )

    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    profile_ctx = await _build_profile_account_context(request, email)
    wallet = profile_ctx["wallet"]

    data = await _get_cached_data()
    guardians = await _guardian_emails()
    columns = [c for c in data["columns"] if c != "email"]
    filtered_rows = [
        row
        for row in data["rows"]
        if str(row.get("email", "")).strip().lower() not in guardians
    ]
    rows = [{k: row.get(k, "") for k in columns} for row in filtered_rows]
    wheel_state = await _wheel_state(email, limit=8)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "columns": columns,
            "rows": rows,
            "source": data["source"],
            "ttl": CACHE_TTL_SECONDS,
            "last_updated": data["cached_at"],
            "project_name": "Interchained × Elara – Ambassadors",
            "pool_balance": data["pool_balance"],
            "wallet": wallet,
            "total_points": data["total_points"],
            "igp_to_itc": data["igp_to_itc"],
            "itc_to_igp": data["itc_to_igp"],
            "show_kyc_toast": profile_ctx["show_kyc_toast"],
            "wheel_state": wheel_state,
        },
    )


@app.get("/gamefi")
async def gamefi(request: Request) -> Any:
    guard = await _maintenance_guard(request)
    if guard:
        return guard

    is_admin = await _current_admin(request)
    if await _maintenance_enabled() and not is_admin:
        return templates.TemplateResponse(
            "maintenance.html",
            {"request": request},
            status_code=503,
        )

    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")

    await _build_profile_account_context(request, email)
    data = await _get_cached_data()
    wheel_state = await _wheel_state(email, limit=10)

    return templates.TemplateResponse(
        "gamefi.html",
        {
            "request": request,
            "project_name": "Interchained × Elara – Ambassadors",
            "pool_balance": data["pool_balance"],
            "source": data["source"],
            "ttl": CACHE_TTL_SECONDS,
            "wheel_state": wheel_state,
        },
    )


@app.get("/api/gamefi/wheel/state")
async def api_wheel_state(request: Request) -> JSONResponse:
    email = await _current_email(request)
    if not email:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    state = await _wheel_state(email, limit=10)
    return JSONResponse({"ok": True, "state": state})


@app.post("/api/gamefi/wheel/spin")
async def api_wheel_spin(request: Request) -> JSONResponse:
    email = await _current_email(request)
    if not email:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    email_norm = _normalize_email(email)
    config = await _ensure_wheel_config()
    if not config["enabled"]:
        return JSONResponse(
            {"ok": False, "error": "wheel_disabled", "detail": "Wheel is currently paused by admins."},
            status_code=423,
        )

    entry_fee = float(config.get("entry_fee", 0.0) or 0.0)
    segments = list(config.get("segments", []))
    cooldown = int(config.get("cooldown_seconds", 0) or 0)

    if entry_fee <= 0:
        return JSONResponse(
            {"ok": False, "error": "invalid_config", "detail": "Entry fee is not configured."},
            status_code=503,
        )
    if not segments:
        return JSONResponse(
            {"ok": False, "error": "invalid_config", "detail": "Reward segments are not configured."},
            status_code=503,
        )

    now = datetime.utcnow()
    if cooldown > 0:
        last_spin_key = f"{WHEEL_LAST_SPIN_PREFIX}{email_norm}"
        last_spin_raw = await redis_client.get(last_spin_key)
        if last_spin_raw:
            last_spin_dt = _parse_iso(last_spin_raw)
            if last_spin_dt is not None:
                elapsed = (now - last_spin_dt).total_seconds()
                if elapsed < cooldown:
                    retry_after = max(int(cooldown - elapsed + 0.999), 1)
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": "cooldown_active",
                            "detail": f"Please wait {retry_after} seconds before spinning again.",
                            "retry_after": retry_after,
                        },
                        status_code=429,
                    )

    user_lock = redis_client.lock(
        f"{WHEEL_USER_LOCK_PREFIX}{email_norm}", timeout=8, blocking=False
    )
    if not await user_lock.acquire(blocking=False):
        return JSONResponse(
            {"ok": False, "error": "spin_in_progress", "detail": "Another spin is already processing."},
            status_code=429,
        )

    global_lock = redis_client.lock(WHEEL_LOCK_KEY, timeout=8, blocking_timeout=4)
    payout = 0.0
    pool_after_fee = 0.0
    balance_after_fee = 0.0
    pool_final = 0.0
    balance_final = 0.0
    segment_index = 0
    segment: dict[str, Any] = {}
    message = ""
    tone = "neutral"
    detail: dict[str, float] = {}
    try:
        try:
            acquired = await global_lock.acquire(blocking=True)
        except LockError:
            acquired = False
        if not acquired:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "busy",
                    "detail": "Casino wheel is busy. Please try again in a moment.",
                },
                status_code=429,
            )

        balance_before = await _scorepad_balance(email_norm)
        if balance_before + 1e-9 < entry_fee:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "insufficient_funds",
                    "detail": "Insufficient IGP on your score pad for this spin.",
                    "scorepad_balance": balance_before,
                },
                status_code=400,
            )

        pipe = redis_client.pipeline()
        pipe.hincrbyfloat("score_pad", email_norm, -entry_fee)
        pipe.hincrbyfloat(WHEEL_CONFIG_KEY, "pool_balance", entry_fee)
        results = await pipe.execute()
        balance_after_fee = float(results[0] or 0.0)
        pool_after_fee = float(results[1] or 0.0)

        try:
            segment_index, segment = _choose_wheel_segment(segments)
        except ValueError:
            revert = redis_client.pipeline()
            revert.hincrbyfloat("score_pad", email_norm, entry_fee)
            revert.hset(WHEEL_CONFIG_KEY, mapping={"pool_balance": pool_after_fee})
            await revert.execute()
            return JSONResponse(
                {"ok": False, "error": "invalid_config", "detail": "Wheel segments unavailable."},
                status_code=503,
            )

        payout, message, tone, detail = _wheel_outcome(segment, entry_fee, pool_after_fee)
        payout = max(0.0, payout)
        pool_final = max(0.0, pool_after_fee - payout)
        balance_final = max(0.0, balance_after_fee + payout)

        adjust_pipe = redis_client.pipeline()
        if payout > 0:
            adjust_pipe.hincrbyfloat("score_pad", email_norm, payout)
        adjust_pipe.hset(WHEEL_CONFIG_KEY, mapping={"pool_balance": pool_final})
        await adjust_pipe.execute()

        if pool_final < -1e-6 or balance_final < -1e-6:
            revert = redis_client.pipeline()
            revert.hincrbyfloat("score_pad", email_norm, entry_fee)
            revert.hset(WHEEL_CONFIG_KEY, mapping={"pool_balance": pool_after_fee})
            if payout > 0:
                revert.hincrbyfloat("score_pad", email_norm, -payout)
            await revert.execute()
            return JSONResponse(
                {
                    "ok": False,
                    "error": "state_conflict",
                    "detail": "Wheel state changed during your spin. Please try again.",
                },
                status_code=409,
            )

        await redis_client.set(
            f"{WHEEL_LAST_SPIN_PREFIX}{email_norm}",
            now.isoformat(),
            ex=max(cooldown, 1) if cooldown else None,
        )
    finally:
        try:
            await global_lock.release()
        except LockError:
            pass
        try:
            await user_lock.release()
        except LockError:
            pass

    history_entry = {
        "email": email_norm,
        "player": _mask_email(email_norm),
        "segment_id": segment.get("id", ""),
        "segment_label": segment.get("label", ""),
        "message": message,
        "tone": tone,
        "entry_fee": entry_fee,
        "payout": payout,
        "pool_balance": pool_final,
        "scorepad_balance": balance_final,
        "detail": detail,
        "created_at": now.isoformat(),
    }
    await _record_wheel_spin(history_entry)

    history = await _wheel_history(10)

    response_payload = {
        "ok": True,
        "segment_index": segment_index,
        "segment": segment,
        "entry_fee": entry_fee,
        "payout": payout,
        "pool_balance": pool_final,
        "scorepad_balance": balance_final,
        "tone": tone,
        "message": message,
        "history": history,
        "cooldown_seconds": cooldown,
    }
    return JSONResponse(response_payload)


@app.get("/api/leaderboard.json")
async def api_leaderboard(request: Request, refresh: bool = Query(False)) -> JSONResponse:
    email = await _current_email(request)
    is_admin = await _current_admin(request)
    if not is_admin and not email:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    if await _maintenance_enabled() and not is_admin:
        return JSONResponse({"ok": False, "error": "maintenance_mode"}, status_code=503)
    data = await _get_cached_data(force_refresh=refresh)
    guardians = await _guardian_emails()
    filtered_rows = [
        row
        for row in data["rows"]
        if str(row.get("email", "")).strip().lower() not in guardians
    ]
    return JSONResponse(
        {
            "ok": True,
            "columns": data["columns"],
            "rows": filtered_rows,
            "source": data["source"],
            "cached_at": data["cached_at"],
            "ttl": CACHE_TTL_SECONDS,
            "pool_balance": data["pool_balance"],
            "total_points": data["total_points"],
            "igp_to_itc": data["igp_to_itc"],
            "itc_to_igp": data["itc_to_igp"],
        }
    )


@app.get("/health")
async def health() -> JSONResponse:
    try:
        data = await _get_cached_data()
        return JSONResponse({
            "ok": True,
            "source": data["source"],
            "pool_balance": data["pool_balance"],
#             "cli": _which_cli(),                       
#             "env_cli": os.getenv("INTERCHAINED_CLI"),  
            "daemon_ready": _daemon_ready(),
            "address": AMBASSADOR_POOL_ADDRESS,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})

__all__ = ["app"]
