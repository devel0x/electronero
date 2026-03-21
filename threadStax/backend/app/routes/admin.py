import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import login_user
from ..models import (
    ApiMessage,
    CreateSeasonRequest,
    FinalizeRequest,
    ModerationRejectRequest,
    SeedJudgesRequest,
    Season,
    SeasonStatusRequest,
    Submission,
    WinnerEntry,
)
from ..rbac import require_role
from ..redis_client import get_redis
from .. import redis_keys

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/season", response_model=Season)
async def create_season(
    payload: CreateSeasonRequest, _: str = Depends(require_role(["admin"]))
) -> Season:
    redis = await get_redis()
    now = datetime.utcnow().isoformat()
    status_value = payload.status or "draft"
    key = redis_keys.season(payload.sid)
    exists = await redis.exists(key)
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Season exists")
    await redis.hset(
        key,
        mapping={"status": status_value, "created_at": now, "ends_at": ""},
    )
    await redis.zadd(redis_keys.seasons(), {payload.sid: datetime.utcnow().timestamp()})
    return Season(sid=payload.sid, status=status_value, created_at=now, ends_at=None)


@router.post("/season/{sid}/status", response_model=Season)
async def set_season_status(
    sid: str, payload: SeasonStatusRequest, _: str = Depends(require_role(["admin"]))
) -> Season:
    redis = await get_redis()
    key = redis_keys.season(sid)
    if not await redis.exists(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    await redis.hset(key, mapping={"status": payload.status})
    data = await redis.hgetall(key)
    return Season(sid=sid, **data)


@router.post("/seed/judges", response_model=ApiMessage)
async def seed_judges(
    payload: SeedJudgesRequest, _: str = Depends(require_role(["admin"]))
) -> ApiMessage:
    for username in payload.usernames:
        await login_user(username.strip(), "judge")
    return ApiMessage(message="Judges seeded")


@router.get("/season/{sid}/moderation/queue", response_model=list[Submission])
async def moderation_queue(
    sid: str, _: str = Depends(require_role(["admin", "moderator"]))
) -> list[Submission]:
    redis = await get_redis()
    sub_ids = await redis.lrange(redis_keys.moderation_queue(sid), 0, -1)
    submissions: list[Submission] = []
    for sub_id in sub_ids:
        data = await redis.hgetall(redis_keys.submission(sid, sub_id))
        if data:
            submissions.append(Submission(sub_id=sub_id, **data))
    return submissions


@router.post("/season/{sid}/submissions/{sub_id}/approve")
async def approve_submission(
    sid: str, sub_id: str, _: str = Depends(require_role(["admin", "moderator"]))
) -> dict:
    redis = await get_redis()
    key = redis_keys.submission(sid, sub_id)
    if not await redis.exists(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    await redis.hset(key, mapping={"status": "approved"})
    await redis.lrem(redis_keys.moderation_queue(sid), 0, sub_id)
    judges = await redis.smembers(redis_keys.role_set("judge"))
    judge_list = list(judges)
    random.shuffle(judge_list)
    assigned = judge_list[:3]
    for judge_uid in assigned:
        await redis.sadd(redis_keys.judge_assigned(sid, judge_uid), sub_id)
    return {"assigned_judges": assigned}


@router.post("/season/{sid}/submissions/{sub_id}/reject", response_model=ApiMessage)
async def reject_submission(
    sid: str,
    sub_id: str,
    payload: ModerationRejectRequest,
    _: str = Depends(require_role(["admin", "moderator"]))
) -> ApiMessage:
    redis = await get_redis()
    key = redis_keys.submission(sid, sub_id)
    if not await redis.exists(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    await redis.hset(key, mapping={"status": "rejected", "review_notes": payload.reason or ""})
    await redis.lrem(redis_keys.moderation_queue(sid), 0, sub_id)
    if payload.reason:
        await redis.sadd(redis_keys.flag(sid, sub_id), payload.reason)
    return ApiMessage(message="Submission rejected")


@router.post("/season/{sid}/finalize", response_model=list[WinnerEntry])
async def finalize_season(
    sid: str, payload: FinalizeRequest, _: str = Depends(require_role(["admin"]))
) -> list[WinnerEntry]:
    redis = await get_redis()
    lb_key = redis_keys.leaderboard(sid)
    top_entries = await redis.zrevrange(lb_key, 0, payload.top_n - 1, withscores=True)
    winners: list[WinnerEntry] = []
    for sub_id, avg in top_entries:
        sub_key = redis_keys.submission(sid, sub_id)
        data = await redis.hgetall(sub_key)
        if not data:
            continue
        await redis.hset(sub_key, mapping={"status": "winner"})
        winners.append(WinnerEntry(sub_id=sub_id, uid=data.get("uid", ""), avg=float(avg)))
    return winners
