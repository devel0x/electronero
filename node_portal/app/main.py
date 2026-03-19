"""Node Operator Rewards Portal.

This module exposes a FastAPI application that monitors node operators
registered in Redis database 6 and calculates their reward share based on
uptime.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import bcrypt
import httpx
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, BaseSettings, Field
from redis.asyncio import Redis
from starlette.middleware.sessions import SessionMiddleware

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    redis_url: str = Field(
        "redis://localhost:6379/6",
        description="Redis connection URL pointing at database 6",
    )
    session_secret: str = Field(
        "change-me",
        description="Secret key used to sign browser sessions.",
    )
    health_check_interval: int = Field(
        60, description="Interval in seconds between node health checks."
    )
    pool_key: str = Field(
        "pool:daily_reward",
        description="Redis key storing the latest reward pool amount.",
    )

    class Config:
        env_prefix = "PORTAL_"


settings = Settings()  # type: ignore[arg-type]


def redis_from_settings() -> Redis:
    """Create a Redis connection scoped to DB 6."""

    return Redis.from_url(settings.redis_url, decode_responses=True)


class NodeRecord(BaseModel):
    """Structured representation of a node registration."""

    email: str
    node_address: str
    p2p_port: int
    rpc_port: int
    wallet_address: str
    status: str
    last_checked: Optional[float]
    last_error: Optional[str]
    uptime_seconds: float
    last_block_height: Optional[int]

    @property
    def rpc_url(self) -> str:
        return f"http://{self.node_address}:{self.rpc_port}"

    @property
    def p2p_endpoint(self) -> str:
        return f"{self.node_address}:{self.p2p_port}"


class NodeRegistry:
    """Encapsulates access patterns to operator data stored in Redis."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def iter_node_keys(self) -> AsyncIterator[str]:
        cursor = "0"
        while cursor:
            cursor, keys = await self._redis.scan(cursor=cursor, match="node:*@*")
            for key in keys:
                yield key
            if cursor == "0":
                break

    async def get_node(self, email: str) -> Optional[NodeRecord]:
        key = self._node_key(email)
        mapping = await self._redis.hgetall(key)
        if not mapping:
            return None
        metrics = await self._redis.hgetall(self._metrics_key(email))
        return self._record_from_mapping(email, mapping, metrics)

    async def list_nodes(self) -> List[NodeRecord]:
        records: List[NodeRecord] = []
        async for key in self.iter_node_keys():
            email = key.split(":", 1)[1]
            record = await self.get_node(email)
            if record:
                records.append(record)
        return records

    async def register_node(self, payload: Dict[str, Any]) -> NodeRecord:
        required_fields = {"email", "node_address", "p2p_port", "rpc_port", "wallet_address"}
        missing = required_fields - payload.keys()
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
        email = payload["email"].lower()
        key = self._node_key(email)
        mapping = {
            "email": email,
            "node_address": payload["node_address"],
            "p2p_port": int(payload["p2p_port"]),
            "rpc_port": int(payload["rpc_port"]),
            "wallet_address": payload["wallet_address"],
            "status": "unknown",
        }
        await self._redis.hset(key, mapping=mapping)
        # Reset metrics on re-registration to avoid stale data.
        await self._redis.delete(self._metrics_key(email))
        record = await self.get_node(email)
        if not record:
            raise RuntimeError("Failed to persist node registration")
        return record

    async def register_success(self, email: str, block_height: Optional[int], duration: float) -> None:
        metrics_key = self._metrics_key(email)
        pipe = self._redis.pipeline()
        pipe.hset(self._node_key(email), mapping={"status": "active", "last_error": ""})
        pipe.hset(
            metrics_key,
            mapping={
                "last_checked": time.time(),
                "last_block_height": block_height or 0,
            },
        )
        pipe.hincrbyfloat(metrics_key, "uptime_seconds", duration)
        pipe.sadd("nodes:active", email)
        pipe.srem("nodes:inactive", email)
        await pipe.execute()

    async def register_failure(self, email: str, error: str) -> None:
        metrics_key = self._metrics_key(email)
        pipe = self._redis.pipeline()
        pipe.hset(
            self._node_key(email),
            mapping={"status": "inactive", "last_error": error[:280]},
        )
        pipe.hset(metrics_key, mapping={"last_checked": time.time()})
        pipe.sadd("nodes:inactive", email)
        pipe.srem("nodes:active", email)
        await pipe.execute()

    async def set_pool_amount(self, amount: float) -> None:
        await self._redis.set(settings.pool_key, f"{amount:.8f}")

    async def get_pool_amount(self) -> float:
        value = await self._redis.get(settings.pool_key)
        if value is None:
            return 0.0
        try:
            return float(value)
        except ValueError:
            logger.warning("Invalid pool amount stored in redis: %s", value)
            return 0.0

    async def get_user_password_hash(self, email: str) -> Optional[str]:
        return await self._redis.hget(self._user_key(email), "password_hash")

    async def set_user_credentials(self, email: str, password: str) -> None:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        await self._redis.hset(
            self._user_key(email),
            mapping={"email": email.lower(), "password_hash": password_hash},
        )

    def _node_key(self, email: str) -> str:
        return f"node:{email.lower()}"

    def _metrics_key(self, email: str) -> str:
        return f"metrics:{email.lower()}"

    def _user_key(self, email: str) -> str:
        return f"user:{email.lower()}"

    def _record_from_mapping(
        self, email: str, mapping: Dict[str, Any], metrics: Dict[str, Any]
    ) -> NodeRecord:
        return NodeRecord(
            email=email,
            node_address=mapping.get("node_address", ""),
            p2p_port=int(mapping.get("p2p_port", 0)),
            rpc_port=int(mapping.get("rpc_port", 0)),
            wallet_address=mapping.get("wallet_address", ""),
            status=mapping.get("status", "unknown"),
            last_checked=float(metrics.get("last_checked", 0.0)) if metrics else None,
            last_error=mapping.get("last_error"),
            uptime_seconds=float(metrics.get("uptime_seconds", 0.0)) if metrics else 0.0,
            last_block_height=int(metrics.get("last_block_height", 0)) if metrics else None,
        )


class NodeHealthMonitor:
    """Background service that pings RPC endpoints and updates uptime metrics."""

    def __init__(self, registry: NodeRegistry, interval: int = 60) -> None:
        self._registry = registry
        self._interval = interval
        self._task: Optional[asyncio.Task[None]] = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._client.aclose()

    async def _run(self) -> None:
        while True:
            start = time.perf_counter()
            try:
                await self.check_all_nodes()
            except Exception:  # pragma: no cover - best effort logging
                logger.exception("Unexpected error during health check")
            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(1, self._interval - int(elapsed)))

    async def check_all_nodes(self) -> None:
        nodes = await self._registry.list_nodes()
        for node in nodes:
            await self._check_node(node)

    async def _check_node(self, node: NodeRecord) -> None:
        start = time.perf_counter()
        try:
            payload = {"jsonrpc": "2.0", "id": "health", "method": "getblockchaininfo"}
            response = await self._client.post(node.rpc_url + "/json_rpc", json=payload)
            response.raise_for_status()
            data = response.json()
            block_height = self._extract_block_height(data)
            duration = time.perf_counter() - start
            await self._registry.register_success(node.email, block_height, duration)
        except Exception as exc:
            await self._registry.register_failure(node.email, str(exc))

    def _extract_block_height(self, payload: Dict[str, Any]) -> Optional[int]:
        try:
            return int(payload.get("result", {}).get("height"))
        except (TypeError, ValueError):
            return None


class RewardShare(BaseModel):
    email: str
    wallet_address: str
    uptime_seconds: float
    weight: float
    payout_amount: float


class RewardCalculator:
    """Derive per-node payout shares from uptime measurements."""

    @staticmethod
    def calculate(nodes: List[NodeRecord], pool_amount: float) -> List[RewardShare]:
        if pool_amount <= 0 or not nodes:
            return [
                RewardShare(
                    email=node.email,
                    wallet_address=node.wallet_address,
                    uptime_seconds=node.uptime_seconds,
                    weight=0.0,
                    payout_amount=0.0,
                )
                for node in nodes
            ]
        total_uptime = sum(max(node.uptime_seconds, 0.0) for node in nodes)
        if total_uptime == 0:
            equal_share = pool_amount / len(nodes)
            return [
                RewardShare(
                    email=node.email,
                    wallet_address=node.wallet_address,
                    uptime_seconds=node.uptime_seconds,
                    weight=1 / len(nodes),
                    payout_amount=equal_share,
                )
                for node in nodes
            ]
        rewards: List[RewardShare] = []
        for node in nodes:
            weight = max(node.uptime_seconds, 0.0) / total_uptime
            rewards.append(
                RewardShare(
                    email=node.email,
                    wallet_address=node.wallet_address,
                    uptime_seconds=node.uptime_seconds,
                    weight=weight,
                    payout_amount=pool_amount * weight,
                )
            )
        return rewards


app = FastAPI(title="Interchained Node Operator Rewards")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, https_only=False)
templates = Jinja2Templates(directory="node_portal/app/templates")


async def get_registry(request: Request) -> NodeRegistry:
    if not hasattr(app.state, "redis"):
        app.state.redis = redis_from_settings()
    if not hasattr(app.state, "registry"):
        app.state.registry = NodeRegistry(app.state.redis)
    return app.state.registry  # type: ignore[return-value]


async def get_monitor(registry: NodeRegistry = Depends(get_registry)) -> NodeHealthMonitor:
    if not hasattr(app.state, "monitor"):
        app.state.monitor = NodeHealthMonitor(registry, interval=settings.health_check_interval)
    return app.state.monitor  # type: ignore[return-value]


def require_login(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return str(user)


@app.on_event("startup")
async def startup_event() -> None:
    registry = await get_registry(Request(scope={"type": "http"}))
    monitor = await get_monitor(registry)
    await monitor.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if hasattr(app.state, "monitor"):
        monitor: NodeHealthMonitor = app.state.monitor  # type: ignore[attr-defined]
        await monitor.stop()
    if hasattr(app.state, "redis"):
        redis: Redis = app.state.redis  # type: ignore[attr-defined]
        await redis.close()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Response:
    if request.session.get("user"):
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})


class LoginForm(BaseModel):
    email: str
    password: str


@app.post("/login")
async def login(request: Request, registry: NodeRegistry = Depends(get_registry)) -> Response:
    form = await request.form()
    email = str(form.get("email", "")).lower()
    password = str(form.get("password", ""))
    password_hash = await registry.get_user_password_hash(email)
    if not password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    if not bcrypt.checkpw(password.encode(), password_hash.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    request.session["user"] = email
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@app.post("/logout")
async def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


class RegisterNodePayload(BaseModel):
    email: str
    node_address: str
    p2p_port: int
    rpc_port: int
    wallet_address: str


@app.post("/nodes", response_model=NodeRecord)
async def register_node(
    payload: RegisterNodePayload,
    user: str = Depends(require_login),
    registry: NodeRegistry = Depends(get_registry),
) -> NodeRecord:
    if payload.email.lower() != user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot register for another operator")
    record = await registry.register_node(payload.dict())
    return record


@app.get("/nodes", response_model=List[NodeRecord])
async def list_nodes(
    user: str = Depends(require_login),
    registry: NodeRegistry = Depends(get_registry),
) -> List[NodeRecord]:
    nodes = await registry.list_nodes()
    return [node for node in nodes if node.email == user]


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: str = Depends(require_login),
    registry: NodeRegistry = Depends(get_registry),
) -> HTMLResponse:
    nodes = await registry.list_nodes()
    user_nodes = [node for node in nodes if node.email == user]
    pool_amount = await registry.get_pool_amount()
    rewards = RewardCalculator.calculate(user_nodes, pool_amount)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "nodes": user_nodes,
            "pool_amount": pool_amount,
            "rewards": rewards,
        },
    )


@app.get("/api/nodes", response_model=List[NodeRecord])
async def api_nodes(
    registry: NodeRegistry = Depends(get_registry),
) -> List[NodeRecord]:
    return await registry.list_nodes()


class PoolUpdate(BaseModel):
    amount: float = Field(..., gt=0)


@app.post("/api/pool")
async def update_pool(
    payload: PoolUpdate,
    user: str = Depends(require_login),
    registry: NodeRegistry = Depends(get_registry),
) -> JSONResponse:
    await registry.set_pool_amount(payload.amount)
    return JSONResponse({"status": "ok", "amount": payload.amount})


@app.get("/api/payouts", response_model=List[RewardShare])
async def payout_preview(
    registry: NodeRegistry = Depends(get_registry),
) -> List[RewardShare]:
    nodes = await registry.list_nodes()
    pool_amount = await registry.get_pool_amount()
    return RewardCalculator.calculate(nodes, pool_amount)


# Utility endpoints -------------------------------------------------------


@app.post("/api/users")
async def create_user(
    payload: LoginForm,
    registry: NodeRegistry = Depends(get_registry),
) -> JSONResponse:
    await registry.set_user_credentials(payload.email, payload.password)
    return JSONResponse({"status": "created", "email": payload.email})


# Ensure contextlib is imported late to avoid issues during cold import.
import contextlib  # noqa: E402  # isort:skip
