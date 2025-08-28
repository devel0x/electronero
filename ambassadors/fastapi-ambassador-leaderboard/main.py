from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Load environment variables
load_dotenv()

SHEET_CSV_URL: str | None = os.getenv("SHEET_CSV_URL")
CSV_PATH: str = os.getenv("CSV_PATH", "data/leaderboard.csv")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "30"))
AMBASSADOR_POOL_ADDRESS: str | None = os.getenv("AMBASSADOR_POOL_ADDRESS")

EXPECTED_COLUMNS = [
    "name",
    "x_handle",
    "points",
    "posts",
    "engagements",
    "referrals",
    "tier",
]

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


def _load_csv() -> None:
    """Load CSV data from Google Sheets or local file into cache."""
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

    cache["columns"] = list(df.columns)
    cache["rows"] = df.astype(str).to_dict(orient="records")
    cache["cached_at"] = datetime.utcnow()
    cache["source"] = source
    cache["pool_balance"] = pool_balance


def _get_cached_data(force_refresh: bool = False) -> Dict[str, Any]:
    now = datetime.utcnow()
    cached_at: datetime | None = cache.get("cached_at")
    if (
        force_refresh
        or cached_at is None
        or now - cached_at > timedelta(seconds=CACHE_TTL_SECONDS)
    ):
        _load_csv()
    return cache


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/")
async def index(request: Request) -> Any:
    data = _get_cached_data()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "columns": data["columns"],
            "rows": data["rows"],
            "source": data["source"],
            "ttl": CACHE_TTL_SECONDS,
            "last_updated": data["cached_at"].isoformat() if data["cached_at"] else "",
            "project_name": "Interchained × Elara – Ambassadors",
            "pool_balance": data["pool_balance"],
        },
    )


@app.get("/api/leaderboard.json")
async def api_leaderboard(refresh: bool = Query(False)) -> JSONResponse:
    data = _get_cached_data(force_refresh=refresh)
    return JSONResponse(
        {
            "ok": True,
            "columns": data["columns"],
            "rows": data["rows"],
            "source": data["source"],
            "cached_at": data["cached_at"].isoformat() if data["cached_at"] else "",
            "ttl": CACHE_TTL_SECONDS,
            "pool_balance": data["pool_balance"],
        }
    )


@app.get("/health")
async def health() -> JSONResponse:
    try:
        _get_cached_data()
        return JSONResponse({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)})


__all__ = ["app"]
