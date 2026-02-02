from fastapi import APIRouter

from ..models import LeaderboardEntry
from ..redis_client import get_redis
from .. import redis_keys

router = APIRouter(prefix="/season", tags=["leaderboard"])


async def _submission_to_entry(sid: str, sub_id: str, score: float) -> LeaderboardEntry | None:
    redis = await get_redis()
    sub_data = await redis.hgetall(redis_keys.submission(sid, sub_id))
    if not sub_data:
        return None
    user_data = await redis.hgetall(redis_keys.user(sub_data.get("uid", "")))
    return LeaderboardEntry(
        sub_id=sub_id,
        uid=sub_data.get("uid", ""),
        username=user_data.get("username", ""),
        threads_url=sub_data.get("threads_url", ""),
        status=sub_data.get("status", "pending"),
        score=score,
    )


@router.get("/{sid}/leaderboard/judges", response_model=list[LeaderboardEntry])
async def leaderboard_judges(sid: str, limit: int = 50) -> list[LeaderboardEntry]:
    redis = await get_redis()
    items = await redis.zrevrange(redis_keys.leaderboard(sid), 0, limit - 1, withscores=True)
    entries: list[LeaderboardEntry] = []
    for sub_id, score in items:
        entry = await _submission_to_entry(sid, sub_id, float(score))
        if entry:
            entries.append(entry)
    return entries


@router.get("/{sid}/leaderboard/votes", response_model=list[LeaderboardEntry])
async def leaderboard_votes(sid: str, limit: int = 50) -> list[LeaderboardEntry]:
    redis = await get_redis()
    items = await redis.zrevrange(redis_keys.vote_leaderboard(sid), 0, limit - 1, withscores=True)
    entries: list[LeaderboardEntry] = []
    for sub_id, score in items:
        entry = await _submission_to_entry(sid, sub_id, float(score))
        if entry:
            entries.append(entry)
    return entries
