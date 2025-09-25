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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable

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

STAKE_TTL_DAYS = 30
STAKE_TTL_SECONDS = STAKE_TTL_DAYS * 24 * 60 * 60
STAKE_DAILY_INTEREST = 0.05
STAKE_UPFRONT_RATIO = 0.25


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

cache: Dict[str, Any] = {
    "columns": [],
    "rows": [],
    "cached_at": None,
    "source": "",
    "pool_balance": 0.0,
}

ACTIVITY_ZSET_PREFIX = "activity:posts:"
ACTIVITY_RESET_KEY = "activity:last_reset"
SCOREPAD_BOOST_POINTS = 1000.0


def _monday_start(dt: datetime | None = None) -> datetime:
    dt = dt or datetime.utcnow()
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


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

    if "email" in df.columns:
        df["email"] = df["email"].astype(str).str.strip().str.lower()
        df["__email_norm"] = df["email"]  # already normalized
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
        pads = await redis_client.hgetall("score_pad")
        norm_map = {k.strip().lower(): float(v) for k, v in pads.items() if v is not None}
        df["points"] = df["points"] + df["__email_norm"].map(norm_map).fillna(0)
    else:
        df["points"] = pd.to_numeric(df.get("points"), errors="coerce").fillna(0)


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
    uniq = sorted(df["points"].unique(), reverse=True)
    rank_map = {v: i + 1 for i, v in enumerate(uniq)}
    df["rank"] = df["points"].map(rank_map).astype(int)

    pool_balance = round(_get_pool_balance(), 8)
    total_points = float(df["points"].sum())
    if total_points > 0:
        df["pending_reward"] = (df["points"] / total_points) * pool_balance
    else:
        df["pending_reward"] = 0.0
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

    df = df.fillna("")
    df["pending_reward"] = df["pending_reward"].apply(lambda x: f"{x:.8f}")

    data = {
        "columns": list(df.columns),
        "rows": df.astype(str).to_dict(orient="records"),
        "cached_at": datetime.utcnow().isoformat(),
        "source": source,
        "pool_balance": pool_balance,
    }
    await redis_client.set(CACHE_KEY, json.dumps(data), ex=CACHE_TTL_SECONDS)
    return data


def _to_lower_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


async def _get_cached_data(force_refresh: bool = False) -> Dict[str, Any]:
    raw = await redis_client.get(CACHE_KEY)
    if force_refresh or raw is None:
        data = await _load_csv()
    else:
        data = json.loads(raw)
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


def _stake_lock_key(email: str, stake_id: str) -> str:
    return f"stake:{email}:{stake_id}"


def _stake_data_key(stake_id: str) -> str:
    return f"stake:data:{stake_id}"


def _stake_index_key(email: str) -> str:
    return f"stakes:{email}"


def _stake_deduction_key(email: str) -> str:
    return f"stake:deduction:{email}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.replace(",", "").strip())
    except Exception:
        return default
    return default


async def _user_leaderboard_stats(email: str) -> dict[str, float]:
    data = await _get_cached_data()
    rows: Iterable[dict[str, Any]] = data.get("rows", [])
    for row in rows:
        row_email = str(row.get("email", "")).strip().lower()
        if row_email == email:
            points = _safe_float(row.get("points"))
            pending_reward = _safe_float(row.get("pending_reward"))
            return {"points": points, "pending_reward": pending_reward}
    return {"points": 0.0, "pending_reward": 0.0}


async def _stake_deduction(email: str) -> float:
    raw = await redis_client.get(_stake_deduction_key(email))
    return _safe_float(raw)


async def _normalize_deduction(email: str) -> None:
    value = await _stake_deduction(email)
    if abs(value) < 1e-9:
        await redis_client.delete(_stake_deduction_key(email))


def _stake_financials(amount: float, days: int = STAKE_TTL_DAYS) -> dict[str, float]:
    projected_final = amount * ((1 + STAKE_DAILY_INTEREST) ** days)
    upfront = amount * STAKE_UPFRONT_RATIO
    payout_on_claim = projected_final - upfront
    bonus_interest = projected_final - amount
    return {
        "projected_final": projected_final,
        "upfront_paid": upfront,
        "payout_on_claim": payout_on_claim,
        "bonus_interest": bonus_interest,
    }


async def _stake_status(email: str, stake_id: str, meta: dict[str, Any]) -> tuple[str, int]:
    stored_status = meta.get("status", "locked")
    if stored_status == "claimed":
        return "claimed", -2
    ttl = await redis_client.ttl(_stake_lock_key(email, stake_id))
    if ttl is None:
        ttl = -2
    if ttl > 0:
        return "locked", ttl
    return "unlocked", ttl


async def _load_stake_meta(stake_id: str) -> dict[str, Any]:
    data = await redis_client.hgetall(_stake_data_key(stake_id))
    if not data:
        return {}
    meta: dict[str, Any] = {**data}
    meta["stake_id"] = stake_id
    meta["amount"] = _safe_float(meta.get("amount"))
    meta["points_snapshot"] = _safe_float(meta.get("points_snapshot"))
    meta["pending_snapshot"] = _safe_float(meta.get("pending_snapshot"))
    meta["projected_final"] = _safe_float(meta.get("projected_final"))
    meta["upfront_paid"] = _safe_float(meta.get("upfront_paid"))
    meta["payout_on_claim"] = _safe_float(meta.get("payout_on_claim"))
    meta["bonus_interest"] = _safe_float(meta.get("bonus_interest"))
    meta["claimed_amount"] = _safe_float(meta.get("claimed_amount"))
    return meta


async def _user_stakes(email: str) -> list[dict[str, Any]]:
    stake_ids = await redis_client.lrange(_stake_index_key(email), 0, -1)
    stakes: list[dict[str, Any]] = []
    for stake_id in stake_ids:
        meta = await _load_stake_meta(stake_id)
        if not meta or meta.get("user") != email:
            continue
        status, ttl = await _stake_status(email, stake_id, meta)
        meta["status"] = status
        meta["seconds_until_unlock"] = ttl if ttl and ttl > 0 else max(ttl, 0)
        stakes.append(meta)
    stakes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return stakes


async def _stake_summary(email: str) -> dict[str, Any]:
    stats = await _user_leaderboard_stats(email)
    deduction = await _stake_deduction(email)
    pending_reward = stats["pending_reward"]
    available = max(pending_reward - deduction, 0.0)
    stakes = await _user_stakes(email)
    return {
        "email": email,
        "points": stats["points"],
        "pending_reward": pending_reward,
        "staked_locked": max(deduction, 0.0),
        "available_pending": available,
        "stakes": stakes,
    }


async def _all_stakes_meta() -> list[dict[str, Any]]:
    stakes: list[dict[str, Any]] = []
    async for key in redis_client.scan_iter("stake:data:*"):
        stake_id = key.split(":", 2)[2]
        meta = await _load_stake_meta(stake_id)
        if meta:
            email = meta.get("user", "")
            if email:
                status, ttl = await _stake_status(email, stake_id, meta)
                meta["status"] = status
                meta["seconds_until_unlock"] = ttl if ttl and ttl > 0 else max(ttl, 0)
            stakes.append(meta)
    stakes.sort(key=lambda x: x.get("created_at", ""))
    return stakes


def _public_stake_record(stake: dict[str, Any]) -> dict[str, Any]:
    return {
        "stake_id": stake.get("stake_id"),
        "user": stake.get("user"),
        "amount": round(float(stake.get("amount", 0.0)), 8),
        "points_snapshot": round(float(stake.get("points_snapshot", 0.0)), 4),
        "pending_snapshot": round(float(stake.get("pending_snapshot", 0.0)), 8),
        "projected_final": round(float(stake.get("projected_final", 0.0)), 8),
        "upfront_paid": round(float(stake.get("upfront_paid", 0.0)), 8),
        "payout_on_claim": round(float(stake.get("payout_on_claim", 0.0)), 8),
        "bonus_interest": round(float(stake.get("bonus_interest", 0.0)), 8),
        "claimed_amount": round(float(stake.get("claimed_amount", 0.0)), 8),
        "created_at": stake.get("created_at"),
        "unlock_at": stake.get("unlock_at"),
        "claimed_at": stake.get("claimed_at"),
        "status": stake.get("status", "locked"),
        "seconds_until_unlock": int(stake.get("seconds_until_unlock", 0) or 0),
    }


def _public_stake_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": summary.get("email"),
        "points": round(float(summary.get("points", 0.0)), 4),
        "pending_reward": round(float(summary.get("pending_reward", 0.0)), 8),
        "staked_locked": round(float(summary.get("staked_locked", 0.0)), 8),
        "available_pending": round(float(summary.get("available_pending", 0.0)), 8),
        "stakes": [_public_stake_record(stake) for stake in summary.get("stakes", [])],
    }


async def _staking_admin_overview() -> dict[str, Any]:
    stakes = await _all_stakes_meta()
    total_staked = sum(stake.get("amount", 0.0) for stake in stakes)
    unlocked_pending = sum(
        stake.get("payout_on_claim", 0.0)
        for stake in stakes
        if stake.get("status") == "unlocked"
    )
    claimed_payouts = sum(
        stake.get("claimed_amount", 0.0) or stake.get("payout_on_claim", 0.0)
        for stake in stakes
        if stake.get("status") == "claimed"
    )
    bonus_interest = sum(
        stake.get("bonus_interest", 0.0)
        for stake in stakes
        if stake.get("status") == "claimed"
    )

    per_user: dict[str, dict[str, Any]] = {}
    for stake in stakes:
        email = stake.get("user") or ""
        if not email:
            continue
        entry = per_user.setdefault(
            email,
            {
                "email": email,
                "total_staked": 0.0,
                "locked": 0.0,
                "unlocked": 0.0,
                "claimed": 0.0,
                "claimed_payouts": 0.0,
                "bonus_interest": 0.0,
            },
        )
        amount = stake.get("amount", 0.0)
        entry["total_staked"] += amount
        status = stake.get("status")
        if status == "locked":
            entry["locked"] += amount
        elif status == "unlocked":
            entry["unlocked"] += amount
        elif status == "claimed":
            entry["claimed"] += amount
            entry["claimed_payouts"] += (
                stake.get("claimed_amount", 0.0)
                or stake.get("payout_on_claim", 0.0)
            )
            entry["bonus_interest"] += stake.get("bonus_interest", 0.0)

    breakdown = [
        {
            **entry,
            "total_staked": round(entry["total_staked"], 8),
            "locked": round(entry["locked"], 8),
            "unlocked": round(entry["unlocked"], 8),
            "claimed": round(entry["claimed"], 8),
            "claimed_payouts": round(entry["claimed_payouts"], 8),
            "bonus_interest": round(entry["bonus_interest"], 8),
        }
        for entry in per_user.values()
    ]
    breakdown.sort(key=lambda x: (-x["total_staked"], x["email"]))

    timeline: dict[str, dict[str, float]] = {}
    for stake in stakes:
        created = stake.get("created_at") or ""
        if created:
            date_key = created[:10]
            bucket = timeline.setdefault(date_key, {"staked": 0.0, "claimed": 0.0})
            bucket["staked"] += stake.get("amount", 0.0)
        if stake.get("status") == "claimed" and stake.get("claimed_at"):
            claim_date = stake["claimed_at"][:10]
            bucket = timeline.setdefault(claim_date, {"staked": 0.0, "claimed": 0.0})
            bucket["claimed"] += (
                stake.get("claimed_amount", 0.0)
                or stake.get("payout_on_claim", 0.0)
            )

    timeline_points = [
        {
            "date": key,
            "staked": round(value["staked"], 8),
            "claimed": round(value["claimed"], 8),
        }
        for key, value in sorted(timeline.items())
    ]

    return {
        "summary": {
            "total_staked": round(total_staked, 8),
            "unlocked_pending": round(unlocked_pending, 8),
            "claimed_payouts": round(claimed_payouts, 8),
            "bonus_interest": round(bonus_interest, 8),
        },
        "stakes": [_public_stake_record(stake) for stake in stakes],
        "by_user": breakdown,
        "timeline": timeline_points,
    }

async def _all_wallets() -> list[dict[str, Any]]:
    wallets: list[dict[str, Any]] = []
    data = await _get_cached_data()
    rows = data.get("rows", [])

    activity_start_ts, activity_end_ts = await _activity_window_bounds()

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

        # normalized email key
        eml = str(row.get("email", "")).strip().lower()
        if eml:
            email_map[eml] = stats

        # normalized telegram key: lowercase, strip @
        tg = str(row.get("telegram", "")).strip()
        if tg:
            tg_norm = tg.lstrip("@").lower()
            if tg_norm:
                tg_map[tg_norm] = stats

    pad_map = await redis_client.hgetall("score_pad")

    keys = await redis_client.keys("user:*")
    for key in keys:
        email = key.split(":", 1)[1]  # already stored lowercased
        udata = await redis_client.hgetall(key)

        # show telegram with leading @ for UI, but use normalized for lookup
        tele_raw = udata.get("telegram", "")
        tele_norm = str(tele_raw).strip().lstrip("@").lower()
        tele_display = f"@{tele_norm}" if tele_norm else ""

        # Prefer email join; if missing, fall back to telegram join
        stats = email_map.get(email) or (tg_map.get(tele_norm) if tele_norm else None)
        if not stats:
            stats = {"points": 0.0, "pending_reward": 0.0}

        deduction = await _stake_deduction(email)
        available_pending = max(stats.get("pending_reward", 0.0) - deduction, 0.0)
        stats = {
            "points": stats.get("points", 0.0),
            "pending_reward": available_pending,
            "staked_locked": max(deduction, 0.0),
        }

        # padding is keyed by normalized email (as you already do)
        try:
            pad_val = float(pad_map.get(email, 0.0))
        except Exception:
            pad_val = 0.0

        # verification: check redis for verified posts or tasks
        verified_posts = await redis_client.scard(f"posts_verified:{email}")
        task_statuses = await redis_client.hvals(f"tasks:{email}")
        task_verified = any(v == "verified" for v in task_statuses)
        is_verified = verified_posts > 0 or task_verified or str(udata.get("verified")) == "1"
        # persist computed status
        await redis_client.hset(f"user:{email}", "verified", int(is_verified))

        activity_key = f"{ACTIVITY_ZSET_PREFIX}{email}"
        weekly_posts = await redis_client.zcount(activity_key, activity_start_ts, activity_end_ts)
        is_active = weekly_posts > 0
        activity_label = "active" if is_active else "inactive"
        await redis_client.hset(f"user:{email}", "activity", activity_label)

        wallets.append(
            {
                "email": email,
                "wallet": udata.get("wallet", ""),
                "telegram": tele_display,
                "tg_link": f"https://t.me/{tele_norm}" if tele_norm else "",
                "points": stats["points"],
                "pending_reward": f"{stats['pending_reward']:.8f}",
                "staked_locked": f"{stats['staked_locked']:.8f}",
                "pad": pad_val,
                "verified": is_verified,
                "verified_posts": verified_posts,
                "active": is_active,
                "activity": activity_label,
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


async def _all_verified_posts() -> list[dict[str, str]]:
    """Return list of verified posts with associated wallet and Telegram."""
    entries: list[dict[str, str]] = []
    keys = await redis_client.keys("posts_verified:*")
    for key in keys:
        email = key.split(":", 1)[1]
        urls = await redis_client.smembers(key)
        udata = await redis_client.hgetall(f"user:{email}")
        tele = udata.get("telegram", "")
        if tele and not tele.startswith("@"):
            tele = f"@{tele.lstrip('@')}"
        wallet = udata.get("wallet", "")
        for url in urls:
            entries.append({"url": url, "telegram": tele, "wallet": wallet})
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


def _normalize_telegram(handle: str) -> str:
    h = handle.strip()
    if not h:
        return ""
    h = h.lstrip("@").lower()
    return f"@{h}"

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
    if email_norm not in REGISTERED_EMAILS:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Email not registered", "msg": ""}
        )
    stored = await redis_client.hgetall(f"user:{email_norm}")
    if not stored or stored.get("password") != _hash_password(password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials", "msg": ""}
        )
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
    return templates.TemplateResponse(
        "register.html", {"request": request, "error": ""}
    )


@app.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    telegram: str = Form(...),
    wallet: str = Form(...),
) -> Any:
    email_norm = email.strip().lower()
    if email_norm not in REGISTERED_EMAILS:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email not permitted"},
        )
    key = f"user:{email_norm}"
    has_created = await redis_client.hexists(key, "created_at")
    await redis_client.hset(
        key,
        mapping={
            "password": _hash_password(password),
            "wallet": wallet.strip(),
            "telegram": _normalize_telegram(telegram),
            "verified": 0,
            **({"created_at": datetime.utcnow().isoformat()} if not has_created else {}),
        },
    )
    return RedirectResponse("/login?msg=Registered+successfully", status_code=303)


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


@app.get("/stake")
async def stake_panel(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    summary = await _stake_summary(email)
    return templates.TemplateResponse(
        "stake.html",
        {
            "request": request,
            "summary": _public_stake_summary(summary),
            "user_email": email,
        },
    )


@app.post("/stake")
async def create_stake(request: Request) -> JSONResponse:
    email = await _current_email(request)
    if not email:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)
    amount = _safe_float(payload.get("amount"))
    if amount <= 0:
        return JSONResponse({"ok": False, "error": "invalid_amount"}, status_code=400)
    summary = await _stake_summary(email)
    available = summary["available_pending"]
    if amount > available + 1e-8:
        return JSONResponse(
            {
                "ok": False,
                "error": "insufficient_pending",
                "available": round(float(available), 8),
            },
            status_code=400,
        )

    now = datetime.utcnow()
    unlock_at = now + timedelta(days=STAKE_TTL_DAYS)
    stake_id = secrets.token_hex(8)
    financials = _stake_financials(amount)

    meta = {
        "stake_id": stake_id,
        "user": email,
        "amount": f"{amount:.8f}",
        "points_snapshot": f"{summary['points']:.4f}",
        "pending_snapshot": f"{summary['pending_reward']:.8f}",
        "projected_final": f"{financials['projected_final']:.8f}",
        "upfront_paid": f"{financials['upfront_paid']:.8f}",
        "payout_on_claim": f"{financials['payout_on_claim']:.8f}",
        "bonus_interest": f"{financials['bonus_interest']:.8f}",
        "created_at": now.isoformat(),
        "unlock_at": unlock_at.isoformat(),
        "status": "locked",
    }
    await redis_client.hset(_stake_data_key(stake_id), mapping=meta)
    await redis_client.set(
        _stake_lock_key(email, stake_id), "locked", ex=STAKE_TTL_SECONDS
    )
    await redis_client.lpush(_stake_index_key(email), stake_id)
    await redis_client.incrbyfloat(_stake_deduction_key(email), amount)
    await redis_client.incrbyfloat("staking:total_staked", amount)
    await redis_client.incrbyfloat("staking:total_upfront", financials["upfront_paid"])
    await redis_client.incrbyfloat(
        "staking:projected_interest", financials["bonus_interest"]
    )

    summary = await _stake_summary(email)
    await _normalize_deduction(email)
    public_summary = _public_stake_summary(summary)
    new_stake = public_summary["stakes"][0] if public_summary["stakes"] else None
    return JSONResponse({"ok": True, "summary": public_summary, "stake": new_stake})


@app.get("/stakes/{user_id}")
async def get_stakes(request: Request, user_id: str) -> JSONResponse:
    email = await _current_email(request)
    user_id_norm = user_id.strip().lower()
    if not email or email != user_id_norm:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    summary = await _stake_summary(email)
    return JSONResponse({"ok": True, "summary": _public_stake_summary(summary)})


@app.post("/stakes/{stake_id}/claim")
async def claim_stake(request: Request, stake_id: str) -> JSONResponse:
    email = await _current_email(request)
    if not email:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    meta = await _load_stake_meta(stake_id)
    if not meta or meta.get("user") != email:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    if meta.get("status") == "claimed":
        return JSONResponse({"ok": False, "error": "already_claimed"}, status_code=400)

    ttl = await redis_client.ttl(_stake_lock_key(email, stake_id))
    if ttl is None:
        ttl = -2
    if ttl > 0:
        return JSONResponse(
            {"ok": False, "error": "stake_locked", "seconds_remaining": ttl},
            status_code=400,
        )

    final_amount = _safe_float(meta.get("projected_final"))
    upfront = _safe_float(meta.get("upfront_paid"))
    amount = _safe_float(meta.get("amount"))
    payout = final_amount - upfront
    claimed_at = datetime.utcnow().isoformat()

    await redis_client.hset(
        _stake_data_key(stake_id),
        mapping={
            "status": "claimed",
            "claimed_at": claimed_at,
            "claimed_amount": f"{payout:.8f}",
        },
    )
    await redis_client.delete(_stake_lock_key(email, stake_id))
    await redis_client.incrbyfloat("staking:claimed_payouts", payout)
    await redis_client.incrbyfloat("staking:claimed_final", final_amount)
    await redis_client.incrbyfloat("staking:claimed_interest", final_amount - amount)
    await redis_client.incrbyfloat(_stake_deduction_key(email), -amount)
    await _normalize_deduction(email)

    summary = await _stake_summary(email)
    public_summary = _public_stake_summary(summary)
    updated = next(
        (s for s in public_summary["stakes"] if s.get("stake_id") == stake_id),
        None,
    )
    return JSONResponse({"ok": True, "summary": public_summary, "stake": updated})


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
        },
    )


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


@app.get("/admin/stats/staking")
async def admin_staking_stats(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    overview = await _staking_admin_overview()
    return JSONResponse({"ok": True, **overview})


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


@app.get("/admin/export/ghost")
async def admin_export_ghost(
    request: Request, fmt: str = Query("json"), ghost: str = Query("")
) -> Response:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    expected = os.getenv("GHOST_EXPORT_KEY")
    if not expected or ghost != expected:
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)

    wallets = await _all_wallets()
    staking_overview = await _staking_admin_overview()
    per_user = {entry["email"]: entry for entry in staking_overview.get("by_user", [])}
    snapshot_map: dict[str, list[dict[str, Any]]] = {}
    for stake in staking_overview.get("stakes", []):
        email = stake.get("user")
        if not email:
            continue
        snapshot_map.setdefault(email, []).append(stake)

    export_rows: list[dict[str, Any]] = []
    for w in wallets:
        email = w.get("email", "")
        breakdown = per_user.get(email, {})
        user_snapshot = snapshot_map.get(email, [])
        outstanding = round(
            breakdown.get("locked", 0.0) + breakdown.get("unlocked", 0.0), 8
        )
        status = "claimed"
        if user_snapshot:
            if any(stake.get("status") == "locked" for stake in user_snapshot):
                status = "locked"
            elif any(stake.get("status") == "unlocked" for stake in user_snapshot):
                status = "unlocked"
            elif any(stake.get("status") == "claimed" for stake in user_snapshot):
                status = "claimed"
        export_rows.append(
            {
                "email": email,
                "wallet": w.get("wallet", ""),
                "telegram": w.get("telegram", ""),
                "points": w.get("points", 0.0),
                "pending_reward": float(w.get("pending_reward", 0.0)),
                "verified": bool(w.get("verified", False)),
                "posts": int(w.get("verified_posts", 0)),
                "activity": str(w.get("activity", "inactive")),
                "staked_amount": outstanding,
                "staking_status": status,
                "stakes_snapshot": user_snapshot,
            }
        )

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
            "staked_amount",
            "staking_status",
            "stakes_snapshot",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in export_rows:
            csv_row = dict(row)
            csv_row["stakes_snapshot"] = json.dumps(row["stakes_snapshot"])
            writer.writerow(csv_row)
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=ambassadors_staking.csv"
            },
        )

    return JSONResponse({"ok": True, "ambassadors": export_rows})


@app.get("/api/admin/posts")
async def api_admin_posts(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    posts = await _all_posts()
    return JSONResponse({"ok": True, "posts": posts})


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
    columns = [c for c in data["columns"] if c != "email"]
    rows = [{k: row.get(k, "") for k in columns} for row in data["rows"]]
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
    return JSONResponse(
        {
            "ok": True,
            "columns": data["columns"],
            "rows": data["rows"],
            "source": data["source"],
            "cached_at": data["cached_at"],
            "ttl": CACHE_TTL_SECONDS,
            "pool_balance": data["pool_balance"],
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
