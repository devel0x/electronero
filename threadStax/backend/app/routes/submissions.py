from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from ..models import SubmitRequest, SubmitResponse, Submission
from ..rbac import require_role
from ..redis_client import get_redis
from .. import redis_keys

router = APIRouter(prefix="/season", tags=["submissions"])


@router.post("/{sid}/submit", response_model=SubmitResponse)
async def submit_entry(
    sid: str,
    payload: SubmitRequest,
    user=Depends(require_role(["participant"])),
) -> SubmitResponse:
    redis = await get_redis()
    if not await redis.exists(redis_keys.season(sid)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    rate_key = redis_keys.rate_limit_submit(user.uid, sid)
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, 60 * 60)
    if count > 5:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Submit rate limit")
    sub_id = uuid4().hex
    now = datetime.utcnow().isoformat()
    data = {
        "uid": user.uid,
        "threads_url": str(payload.threads_url),
        "code_phrase": payload.code_phrase,
        "status": "pending",
        "created_at": now,
        "review_notes": "",
    }
    await redis.hset(redis_keys.submission(sid, sub_id), mapping=data)
    await redis.zadd(redis_keys.submissions(sid), {sub_id: datetime.utcnow().timestamp()})
    await redis.zadd(redis_keys.user_submissions(user.uid, sid), {sub_id: datetime.utcnow().timestamp()})
    await redis.rpush(redis_keys.moderation_queue(sid), sub_id)
    return SubmitResponse(sub_id=sub_id)


@router.get("/{sid}/submissions/mine", response_model=list[Submission])
async def my_submissions(
    sid: str, user=Depends(require_role(["participant"]))
) -> list[Submission]:
    redis = await get_redis()
    sub_ids = await redis.zrevrange(redis_keys.user_submissions(user.uid, sid), 0, -1)
    submissions: list[Submission] = []
    for sub_id in sub_ids:
        data = await redis.hgetall(redis_keys.submission(sid, sub_id))
        if not data:
            continue
        agg = await redis.hgetall(redis_keys.score_agg(sid, sub_id))
        score = float(agg.get("avg")) if agg.get("avg") else None
        submissions.append(Submission(sub_id=sub_id, agg_score=score, **data))
    return submissions
