from __future__ import annotations

import json
import re
import os, json, shutil, shlex, subprocess
import secrets
import hashlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
import csv
import io

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
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
            return float(data.get("total_amount", 0.0))
    except subprocess.CalledProcessError as e:
        print(f"[pool_balance] scantxoutset failed: {e.stderr.strip()}")
    except Exception as e:
        print(f"[pool_balance] scantxoutset error: {e}")
    if RPC_WALLET:
        try:
            cp = _run_cli(f"-rpcwallet={RPC_WALLET}", "getbalance")
            return float(cp.stdout.strip())
        except Exception as e:
            print(f"[pool_balance] getbalance (wallet) error: {e}")
    try:
        cp = _run_cli("getreceivedbyaddress", addr, "0")
        return float(cp.stdout.strip())
    except Exception as e:
        print(f"[pool_balance] getreceivedbyaddress error: {e}")
    return 250.0

async def _load_csv() -> Dict[str, Any]:
    """Load CSV data from Google Sheets or local file and cache in Redis."""
    path = SHEET_CSV_URL or CSV_PATH
    source = "google_sheet" if SHEET_CSV_URL else "local_csv"

    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to read CSV from {path}: {exc}") from exc

    df.columns = [c.strip() for c in df.columns]

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if "rank" in df.columns:
        df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
        df = df.sort_values("rank", ascending=True)
    else:
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)
        df = df.sort_values("points", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))

    # apply extra admin points if email column present
    if "email" in df.columns:
        df["email"] = df["email"].fillna("").astype(str).str.strip().str.lower()
        extras = await redis_client.hgetall("extra_points")
        df["extra_points"] = df["email"].map(lambda e: float(extras.get(e, 0.0)))
        df["points"] = df["points"] + df["extra_points"]
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

    base_cols = [
        "rank",
        "name",
        "email",
        "telegram",
        "points",
        "tier",
        "pending_reward",
    ]
    other_cols = [c for c in df.columns if c not in base_cols]
    df = df[[c for c in base_cols if c in df.columns]]
    # df = df[base_cols + other_cols]

    df = df.fillna("")
    df["pending_reward"] = df["pending_reward"].apply(lambda x: f"{x:.8f}")

    columns = [c for c in df.columns if c != "email"]
    data = {
        "columns": columns,
        "rows": df.astype(str).to_dict(orient="records"),
        "cached_at": datetime.utcnow().isoformat(),
        "source": source,
        "pool_balance": pool_balance,
    }
    await redis_client.set(CACHE_KEY, json.dumps(data), ex=CACHE_TTL_SECONDS)
    return data


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


async def _pending_rewards_map() -> dict[str, float]:
    mapping: dict[str, float] = {}
    data = await _get_cached_data()
    rows = data.get("rows", [])
    for row in rows:
        email = str(row.get("email", "")).strip().lower()
        if email:
            try:
                mapping[email] = float(row.get("pending_reward", 0))
            except Exception:
                mapping[email] = 0.0
    return mapping


async def _all_wallets() -> list[dict[str, str]]:
    wallets: list[dict[str, str]] = []
    pending_map = await _pending_rewards_map()
    cached = await _get_cached_data()
    rows = cached.get("rows", [])
    base_points: dict[str, float] = {}
    for row in rows:
        e = str(row.get("email", "")).strip().lower()
        try:
            base_points[e] = float(row.get("points", 0))
        except Exception:
            base_points[e] = 0.0
    extras_raw = await redis_client.hgetall("extra_points")
    extras = {k: float(v) for k, v in extras_raw.items()}
    keys = await redis_client.keys("user:*")
    for key in keys:
        email = key.split(":", 1)[1]
        data = await redis_client.hgetall(key)
        tele = data.get("telegram", "")
        if tele and not tele.startswith("@"):
            tele = f"@{tele.lstrip('@')}"
        reward = pending_map.get(email, 0.0)
        extra = extras.get(email, 0.0)
        total = base_points.get(email, 0.0)
        wallets.append(
            {
                "email": email,
                "wallet": data.get("wallet", ""),
                "telegram": tele,
                "pending_reward": f"{reward:.8f}",
                "points": f"{total:.2f}",
                "extra_points": f"{extra:.2f}",
            }
        )
    return wallets


async def _all_posts() -> dict[str, list[dict[str, Any]]]:
    posts: dict[str, list[dict[str, Any]]] = {}
    keys = await redis_client.keys("posts:*")
    for key in keys:
        email = key.split(":", 1)[1].strip().lower()
        urls = await redis_client.lrange(key, 0, -1)
        verified = await redis_client.smembers(f"posts_verified:{email}")
        safe_verified = {str(v).strip() for v in verified}
        posts[email] = [
            {"url": str(u).strip(), "verified": str(u).strip() in safe_verified}
            for u in urls if u
        ]
    return posts

async def _all_tasks() -> dict[str, dict[str, str]]:
    tasks: dict[str, dict[str, str]] = {}
    keys = await redis_client.keys("tasks:*")
    for key in keys:
        email = key.split(":", 1)[1]
        tasks[email] = await redis_client.hgetall(key)
    return tasks

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _normalize_telegram(handle: str) -> str:
    h = handle.strip()
    if not h:
        return ""
    h = h.lstrip("@")
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
    await redis_client.hset(
        f"user:{email_norm}",
        mapping={
            "password": _hash_password(password),
            "wallet": wallet.strip(),
            "telegram": _normalize_telegram(telegram),
        },
    )
    return RedirectResponse("/login?msg=Registered+successfully", status_code=303)


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
    posts = await redis_client.lrange(f"posts:{email}", 0, -1)
    return templates.TemplateResponse(
        "verify.html", {"request": request, "posts": posts, "error": ""}
    )


@app.post("/verify")
async def verify_submit(request: Request, url: str = Form(...)) -> RedirectResponse:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    url_clean = url.strip()
    if url_clean:
        await redis_client.lpush(f"posts:{email}", url_clean)
    return RedirectResponse("/verify", status_code=303)


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
    wallets = await _all_wallets()
    posts = await _all_posts()
    tasks = await _all_tasks()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "wallets": wallets,
            "posts": posts,
            "tasks": tasks,
            "task_labels": TASK_LABELS,
        },
    )


@app.get("/api/admin/wallets")
async def api_admin_wallets(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    wallets = await _all_wallets()
    return JSONResponse({"ok": True, "wallets": wallets})


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

    if verify_all:
        # Works with BOTH shapes:
        #   { email: [ {"url": "...", "verified": bool}, ... ] }
        #   { email: [ "https://...", ... ] }
        posts = await _all_posts()
        for eml, entries in posts.items():
            eml_key = eml.strip().lower()
            for entry in entries:
                if isinstance(entry, dict):
                    u = entry.get("url", "")
                else:
                    u = entry
                u = _clean_url(u)
                if u:
                    pipe.sadd(f"posts_verified:{eml_key}", u)

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

    if pipe.command_stack:
        await pipe.execute()

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


@app.post("/admin/points/add")
async def admin_points_add(
    request: Request, email: str = Form(...), points: float = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    try:
        delta = float(points)
    except Exception:
        delta = 0.0
    if delta:
        await redis_client.hincrbyfloat("extra_points", email.strip().lower(), delta)
        await redis_client.delete(CACHE_KEY)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/tasks/verify")
async def admin_task_verify(
    request: Request, email: str = Form(...), task_id: str = Form(...)
) -> RedirectResponse:
    if not await _current_admin(request):
        return RedirectResponse("/admin/login")
    await redis_client.hset(f"tasks:{email}", task_id, "verified")
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


@app.get("/api/admin/leaderboard.json")
async def api_admin_leaderboard_json(request: Request) -> JSONResponse:
    if not await _current_admin(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    wallets = await _all_wallets()
    rows = [
        {"email": w["email"], "wallet": w["wallet"], "telegram": w["telegram"], "points": w["points"]}
        for w in wallets
    ]
    return JSONResponse({"ok": True, "rows": rows})


@app.get("/api/admin/leaderboard.csv")
async def api_admin_leaderboard_csv(request: Request) -> Response:
    if not await _current_admin(request):
        return Response("unauthorized", status_code=401)
    wallets = await _all_wallets()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["email", "wallet", "telegram", "points"])
    writer.writeheader()
    for w in wallets:
        writer.writerow({k: w.get(k, "") for k in ["email", "wallet", "telegram", "points"]})
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leaderboard.csv"},
    )


@app.get("/")
async def index(request: Request) -> Any:
    email = await _current_email(request)
    if not email:
        return RedirectResponse("/login")
    user = await redis_client.hgetall(f"user:{email}")
    wallet = user.get("wallet") if user else ""
    data = await _get_cached_data()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "columns": data["columns"],
            "rows": data["rows"],
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
    if not await _current_email(request):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
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
