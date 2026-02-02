from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .redis_client import get_redis
from .routes import admin, auth, judge, leaderboard, seasons, submissions, vote

app = FastAPI(title="Threads Contest Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    redis = await get_redis()
    await redis.ping()


app.include_router(auth.router)
app.include_router(seasons.router)
app.include_router(submissions.router)
app.include_router(admin.router)
app.include_router(judge.router)
app.include_router(vote.router)
app.include_router(leaderboard.router)
