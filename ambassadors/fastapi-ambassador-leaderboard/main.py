from __future__ import annotations

import json
import os
import secrets
import hashlib
import subprocess
from datetime import datetime

from pathlib import Path
from typing import Any, Dict

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis


# Load environment variables
load_dotenv()

SHEET_CSV_URL: str | None = os.getenv("SHEET_CSV_URL")
CSV_PATH: str = os.getenv("CSV_PATH", "data/leaderboard.csv")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "30"))
AMBASSADOR_POOL_ADDRESS: str | None = os.getenv("AMBASSADOR_POOL_ADDRESS")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REGISTRATIONS_CSV: str = os.getenv("REGISTRATIONS_CSV", "data/registrations.csv")
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))


EXPECTED_COLUMNS = [
    "name",
    "x_handle",
    "points",
    "posts",
    "engagements",
    "referrals",
    "tier",
]

redis_client: Redis = Redis.from_url(REDIS_URL, decode_responses=True)
CACHE_KEY = "leaderboard_cache"


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


def _get_pool_balance() -> float:
    """Fetch ITC balance for the ambassador pool address via interchained-cli."""
    if not AMBASSADOR_POOL_ADDRESS:
        return 0.0
    try:
        result = subprocess.run(
            ["interchained-cli", "getbalance", AMBASSADOR_POOL_ADDRESS],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


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
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0)

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
        "x_handle",
        "points",
        "posts",
        "engagements",
        "referrals",
        "tier",
        "pending_reward",
    ]
    other_cols = [c for c in df.columns if c not in base_cols]
    df = df[base_cols + other_cols]

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


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


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
        mapping={"password": _hash_password(password), "wallet": wallet.strip()},
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
        await _get_cached_data()
        return JSONResponse({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)})


__all__ = ["app"]
