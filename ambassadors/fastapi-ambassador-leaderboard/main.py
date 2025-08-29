from __future__ import annotations

import os
import os, json, shutil, shlex, subprocess
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
INTERCHAINED_CLI = os.getenv("INTERCHAINED_CLI", "interchained-cli")
CLI_EXTRA = os.getenv("CLI_EXTRA", "")
RPC_WALLET = os.getenv("RPC_WALLET")
CLI_TIMEOUT = float(os.getenv("CLI_TIMEOUT", "6.0"))
RANK_MODE = os.getenv("RANK_MODE", "competition").lower()

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
        return 0.0
    if not _daemon_ready():
        return 0.0
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
        "telegram",
        # "x_handle",
        "points",
        # "posts",
        # "engagements",
        # "referrals",
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
            "project_name": "Interchained × Elara – Governance",
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
        data = _get_cached_data()
        return JSONResponse({
            "ok": True,
            "source": data["source"],
            "pool_balance": data["pool_balance"],
            "cli": _which_cli(),                       # resolved full path or None
            "env_cli": os.getenv("INTERCHAINED_CLI"),  # raw env value
            "daemon_ready": _daemon_ready(),
            "address": AMBASSADOR_POOL_ADDRESS,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})
    
__all__ = ["app"]
