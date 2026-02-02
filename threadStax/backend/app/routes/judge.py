from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..models import AssignedSubmission, ScoreRequest
from ..rbac import require_role
from ..redis_client import get_redis
from .. import redis_keys

router = APIRouter(prefix="/judge", tags=["judge"])


@router.get("/season/{sid}/assigned", response_model=list[AssignedSubmission])
async def assigned_submissions(
    sid: str, user=Depends(require_role(["judge"]))
) -> list[AssignedSubmission]:
    redis = await get_redis()
    sub_ids = await redis.smembers(redis_keys.judge_assigned(sid, user.uid))
    results: list[AssignedSubmission] = []
    for sub_id in sub_ids:
        sub_data = await redis.hgetall(redis_keys.submission(sid, sub_id))
        if not sub_data:
            continue
        score_data = await redis.hgetall(redis_keys.score(sid, sub_id, user.uid))
        judge_score = int(score_data["score"]) if score_data.get("score") else None
        results.append(
            AssignedSubmission(
                sub_id=sub_id,
                uid=sub_data.get("uid", ""),
                threads_url=sub_data.get("threads_url", ""),
                code_phrase=sub_data.get("code_phrase", ""),
                status=sub_data.get("status", "pending"),
                created_at=sub_data.get("created_at", ""),
                judge_score=judge_score,
                judge_notes=score_data.get("notes"),
            )
        )
    return results


@router.post("/season/{sid}/score/{sub_id}")
async def score_submission(
    sid: str,
    sub_id: str,
    payload: ScoreRequest,
    user=Depends(require_role(["judge"]))
) -> dict:
    redis = await get_redis()
    sub_key = redis_keys.submission(sid, sub_id)
    if not await redis.exists(sub_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    score_key = redis_keys.score(sid, sub_id, user.uid)
    agg_key = redis_keys.score_agg(sid, sub_id)
    async with redis.pipeline(transaction=True) as pipe:
        existing = await redis.hgetall(score_key)
        current = await redis.hgetall(agg_key)
        sum_value = float(current.get("sum", 0))
        count_value = int(current.get("count", 0))
        if existing and existing.get("score") is not None:
            sum_value -= float(existing.get("score"))
        else:
            count_value += 1
        sum_value += payload.score
        avg = sum_value / count_value if count_value else 0.0
        now = datetime.utcnow().isoformat()
        pipe.hset(score_key, mapping={"score": payload.score, "notes": payload.notes or "", "updated_at": now})
        pipe.hset(agg_key, mapping={"sum": sum_value, "count": count_value, "avg": avg, "finalized": ""})
        pipe.zadd(redis_keys.leaderboard(sid), {sub_id: avg})
        await pipe.execute()
    return {"avg": avg, "sum": sum_value, "count": count_value}
