from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PyDesk FastAPI Backend", version="0.1.0")


class PingResponse(BaseModel):
    message: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ping", response_model=PingResponse)
def ping() -> PingResponse:
    return PingResponse(message="Hello from FastAPI backend")
