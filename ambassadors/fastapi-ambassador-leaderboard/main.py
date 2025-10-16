from __future__ import annotations

import json
import re
import ipaddress
import os, json, shutil, shlex, subprocess
import secrets
import hashlib
import subprocess
import csv
import io
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote_plus

import pandas as pd
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis


# Load environment variables
load_dotenv()

EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
SHEET_CSV_URL: str | None = os.getenv("SHEET_CSV_URL")
CSV_PATH: str = os.getenv("CSV_PATH", "data/leaderboard.csv")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "30"))
AMBASSADOR_POOL_ADDRESS: str | None = os.getenv("AMBASSADOR_POOL_ADDRESS")

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
PENDING_VERIFICATION_MIGRATION_KEY = "referrals:migration:pending_all_v1"
MIGRATIONS_DIR = Path(os.getenv("MIGRATIONS_DIR", "data/migrations")).resolve()
PENDING_VERIFICATION_MIGRATION_SENTINEL = (
    MIGRATIONS_DIR / "pending_all_v1.complete"
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

ACTIVITY_ZSET_PREFIX = "activity:posts:"
ACTIVITY_RESET_KEY = "activity:last_reset"
SCOREPAD_BOOST_POINTS = 1000.0
TRANSFER_HISTORY_LIMIT = int(os.getenv("TRANSFER_HISTORY_LIMIT", "100"))
GLOBAL_TRANSFER_HISTORY_LIMIT = int(os.getenv("GLOBAL_TRANSFER_HISTORY_LIMIT", "500"))
VERIFIED_SEARCH_LIMIT = int(os.getenv("VERIFIED_SEARCH_LIMIT", "50"))
TRANSFER_GLOBAL_LOG_KEY = "transfers:global"
GUARDIAN_SET_KEY = "guardians:emails"
GUARDIAN_USER_FIELD = "guardian"


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

def _get_pool_balance() -> float:
    addr = AMBASSADOR_POOL_ADDRESS
    if not addr:
        return 250.0
    if not _daemon_ready():
        return 250.0
    try:
        cp = _run_cli("scantxoutset", "start", f'["addr({addr})"]')
        data = json.loads(cp.stdout)
        if data.get("success"):
            base_amount = float(data.get("total_amount", 0.0))
            ops_amount = base_amount * 3000 / 10000
            operations_reserve = 300
            true_amount = base_amount - ops_amount - operations_reserve
            return true_amount
    except subprocess.CalledProcessError as e:
        print(f"[pool_balance] scantxoutset failed: {e.stderr.strip()}")
    except Exception as e:
        print(f"[pool_balance] scantxoutset error: {e}")
    if RPC_WALLET:
        try:
            cp = _run_cli(f"-rpcwallet={RPC_WALLET}", "getbalance")
            base_amount = float(cp.stdout.strip())
            ops_amount = base_amount * 3000 / 10000
            operations_reserve = 300
            true_amount = base_amount - ops_amount - operations_reserve
            return true_amount
        except Exception as e:
            print(f"[pool_balance] getbalance (wallet) error: {e}")
    try:
        cp = _run_cli("getreceivedbyaddress", addr, "0")
        base_amount = float(cp.stdout.strip())
        ops_amount = base_amount * 3000 / 10000
        operations_reserve = 300
        true_amount = base_amount - ops_amount - operations_reserve
        return true_amount
    except Exception as e:
        print(f"[pool_balance] getreceivedbyaddress error: {e}")
    return 250.0

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

    pool_balance = round(_get_pool_balance(), 8)
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
            }
        )

    return wallets


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

    payload.update({
        "email": referred_norm,
        "status": status,
    })
    timestamp = datetime.utcnow().isoformat()
    if status == "approved":
        payload["approved_at"] = timestamp
    elif status == "rejected":
        payload["rejected_at"] = timestamp

    await redis_client.hset(key, referred_norm, json.dumps(payload))
    entries = await _referral_entries(referrer_norm)
    count = sum(1 for entry in entries if entry.get("status") != "rejected")
    await redis_client.hset(
        f"user:{referrer_norm}", mapping={"referral_count": count}
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
    """Mark all existing ambassadors as pending for a one-time review sweep."""

    # Check sentinel (already run)
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
            PENDING_VERIFICATION_MIGRATION_KEY,
            datetime.utcnow().isoformat(),
            nx=True
        )
        return

    try:
        # ✅ Pass 1: process user hashes safely
        async for key in redis_client.scan_iter("user:*"):
            try:
                # key is already a string in aioredis/redis-py ≥ 4.0
                if isinstance(key, bytes):
                    key = key.decode()

                # ✅ Type check
                key_type = await redis_client.type(key)
                if isinstance(key_type, bytes):
                    key_type = key_type.decode()
                if key_type != "hash":
                    print(f"[migration] skipping {key} - not a hash ({key_type})")
                    continue

                # ✅ Extract user ID part
                identifier = key.split("user:", 1)[1].strip()

                # ✅ Skip non-email keys (numeric, bot IDs, etc.)
                if not EMAIL_RE.match(identifier):
                    print(f"[migration] skipping non-email key: {key}")
                    continue

                # ✅ Reset verification state
                await redis_client.hset(key, mapping={"verified": 0})
                await redis_client.hdel(key, "verified_at")

            except Exception as inner_exc:
                print(f"[migration] skipping {key} due to error: {inner_exc}")

        # ✅ Pass 2: normalize all referrals to 'pending'
        async for key in redis_client.scan_iter(f"{REFERRALS_HASH_PREFIX}*"):
            if isinstance(key, bytes):
                key = key.decode()

            referrer = key.split(":", 1)[1].strip().lower()
            raw_map = await redis_client.hgetall(key)
            updates: dict[str, str] = {}

            for referred_email, raw in raw_map.items():
                if isinstance(referred_email, bytes):
                    referred_email = referred_email.decode()
                if isinstance(raw, bytes):
                    raw = raw.decode()

                try:
                    payload = json.loads(raw)
                except Exception:
                    continue

                status = str(payload.get("status", "")).strip().lower()
                if status != "pending":
                    payload["status"] = "pending"
                    payload.pop("approved_at", None)
                    payload.pop("rejected_at", None)
                    updates[referred_email] = json.dumps(payload)

            if updates:
                await redis_client.hset(key, mapping=updates)

            if referrer:
                entries = await _referral_entries(referrer)
                count = sum(1 for entry in entries if entry.get("status") != "rejected")
                await redis_client.hset(f"user:{referrer}", mapping={"referral_count": count})

        # ✅ Pass 3: mark migration as done
        await redis_client.set(
            PENDING_VERIFICATION_MIGRATION_KEY,
            datetime.utcnow().isoformat()
        )
        try:
            MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
            PENDING_VERIFICATION_MIGRATION_SENTINEL.write_text(
                datetime.utcnow().isoformat(),
                encoding="utf-8"
            )
        except Exception:
            print("[migration] failed to persist sentinel flag to disk")

    except Exception as exc:
        print(f"[migration] failed to queue existing ambassadors for review: {exc}")
        

async def _pending_referrals() -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    async for key in redis_client.scan_iter("user:*"):
        email = key.split(":", 1)[1].strip().lower()
        data = await redis_client.hgetall(key)
        if not data:
            continue
        if str(data.get("verified", "0")) == "1":
            continue

        referred_by = str(data.get("referred_by", "")).strip().lower()
        created_at = str(data.get("created_at", ""))
        joined_at = str(data.get("referred_at", "")) or created_at
        status = "pending"
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
                "status": status or "pending",
                "created_at": created_at,
                "joined_at": joined_at,
                "joined_at_display": _format_timestamp(joined_at),
                "email_opt_in": str(data.get("email_opt_in", "0")) in {"1", "true", "yes"},
            }
        )

    pending.sort(key=lambda item: item.get("joined_at", ""), reverse=True)
    return pending


def _ensure_leaderboard_entry(email: str, telegram: str) -> None:
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return
    tele_norm = _normalize_telegram(telegram)
    username = tele_norm.lstrip("@") if tele_norm else ""
    path = Path(CSV_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
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

    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames:
                fieldnames = reader.fieldnames
            for row in reader:
                rows.append(dict(row))

    found = False
    for row in rows:
        row_email = str(row.get("email", "")).strip().lower()
        if row_email == email_norm:
            if tele_norm:
                row["telegram"] = tele_norm
            if username:
                row["name"] = username
            if "tier" in row and not str(row.get("tier", "")).strip():
                row["tier"] = "Ambassador"
            for key in ("points", "posts", "engagements", "referrals"):
                if key in row and not str(row.get(key, "")).strip():
                    row[key] = "0"
            found = True
            break

    if not found:
        new_row = {key: "" for key in fieldnames}
        new_row.update(
            {
                "name": username or (email_norm.split("@")[0] if "@" in email_norm else email_norm),
                "telegram": tele_norm,
                "points": "0",
                "tier": "Ambassador",
                "posts": "0",
                "engagements": "0",
                "referrals": "0",
                "email": email_norm,
            }
        )
        rows.append(new_row)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


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
    user = await redis_client.hgetall(f"user:{email}")
    return templates.TemplateResponse(
        "wallet.html", {"request": request, "error": "", "wallet": user.get("wallet", "")}
    )


@app.post("/wallet")
async def wallet_update(request: Request, wallet: str = Form(...)) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    await redis_client.hset(f"user:{email}", mapping={"wallet": wallet.strip()})
    return RedirectResponse("/", status_code=303)


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
                "history": history,
                "totals": totals,
            },
        )

    history = await _transfer_history(email)
    totals = _transfer_totals(history)
    pad_balance = await _scorepad_balance(email)
    available_points = float(profile.get("points", 0.0))
    if profile.get("guardian"):
        available_points = max(pad_balance, 0.0)
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

    source_pad_balance = await _scorepad_balance(email)
    available_points = float(source_profile.get("points", 0.0))
    if source_profile.get("guardian"):
        available_points = max(source_pad_balance, 0.0)
    if amount_value > available_points:
        return await transfers_page(
            request,
            error="Transfer exceeds your available points.",
        )

    receiver_email = destination_profile.get("email") or ""
    if not receiver_email:
        return await transfers_page(request, error="Destination ambassador is missing an email. Contact support.")

    dest_pad_balance = await _scorepad_balance(receiver_email)
    receiver_points_before = float(destination_profile.get("points", 0.0))
    if destination_profile.get("guardian"):
        receiver_points_before = max(dest_pad_balance, 0.0)

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
    maintenance_enabled = await _maintenance_enabled()
    transfers = await _all_transfer_history()
    pending_referrals = await _pending_referrals()
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
            "transfers": transfers,
            "verified_search_limit": VERIFIED_SEARCH_LIMIT,
            "pending_referrals": pending_referrals,
        },
    )


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
    email_norm = str(email or "").strip().lower()
    if not email_norm:
        return False

    removed_from_leaderboard = _remove_leaderboard_entry(email_norm)

    key = f"user:{email_norm}"
    data = await redis_client.hgetall(key)
    if data:
        referrer = str(data.get("referred_by", "")).strip().lower()
        if referrer:
            await _set_referral_status(referrer, email_norm, "rejected")

        referral_code = str(data.get("referral_code", "")).strip().upper()
        if referral_code:
            await redis_client.delete(f"{REFERRAL_CODE_KEY_PREFIX}{referral_code}")

        await redis_client.delete(key)
        await redis_client.delete(f"recovery:{email_norm}")
        await redis_client.delete(f"posts:{email_norm}")
        await redis_client.delete(f"posts_verified:{email_norm}")
        await redis_client.delete(f"posts_rejected:{email_norm}")
        await redis_client.delete(f"tasks:{email_norm}")
        await redis_client.delete(f"transfers:{email_norm}")
        await redis_client.delete(f"{ACTIVITY_ZSET_PREFIX}{email_norm}")

    _unregister_email_record(email_norm)

    return removed_from_leaderboard


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

    user = await redis_client.hgetall(f"user:{email}")
    wallet = user.get("wallet") if user else ""
    data = await _get_cached_data()
    guardians = await _guardian_emails()
    columns = [c for c in data["columns"] if c != "email"]
    filtered_rows = [
        row
        for row in data["rows"]
        if str(row.get("email", "")).strip().lower() not in guardians
    ]
    rows = [{k: row.get(k, "") for k in columns} for row in filtered_rows]
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
        },
    )


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
