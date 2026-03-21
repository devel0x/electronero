from fastapi import APIRouter, HTTPException, status

from ..models import Season
from ..redis_client import get_redis
from .. import redis_keys

router = APIRouter(prefix="/season", tags=["season"])


@router.get("", response_model=list[Season])
async def list_seasons() -> list[Season]:
    redis = await get_redis()
    entries = await redis.zrange(redis_keys.seasons(), 0, -1, withscores=False)
    seasons: list[Season] = []
    for sid in entries:
        data = await redis.hgetall(redis_keys.season(sid))
        if data:
            seasons.append(Season(sid=sid, **data))
    return seasons


@router.get("/{sid}", response_model=Season)
async def get_season(sid: str) -> Season:
    redis = await get_redis()
    data = await redis.hgetall(redis_keys.season(sid))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return Season(sid=sid, **data)
