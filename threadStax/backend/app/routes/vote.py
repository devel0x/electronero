from fastapi import APIRouter, Depends, HTTPException, status

from ..models import VoteResponse
from ..rbac import require_role
from ..redis_client import get_redis
from .. import redis_keys

router = APIRouter(prefix="/season", tags=["vote"])


@router.post("/{sid}/vote/{sub_id}", response_model=VoteResponse)
async def vote_submission(
    sid: str, sub_id: str, user=Depends(require_role(["voter"]))
) -> VoteResponse:
    redis = await get_redis()
    if not await redis.exists(redis_keys.submission(sid, sub_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    rate_key = redis_keys.rate_limit_vote(user.uid, sid)
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, 60 * 60)
    if count > 50:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Vote rate limit")
    vote_set_key = redis_keys.vote_set(sid, sub_id)
    vote_count_key = redis_keys.vote_count(sid, sub_id)
    vlb_key = redis_keys.vote_leaderboard(sid)
    async with redis.pipeline(transaction=True) as pipe:
        while True:
            try:
                await pipe.watch(vote_set_key)
                if await pipe.sismember(vote_set_key, user.uid):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already voted")
                pipe.multi()
                pipe.sadd(vote_set_key, user.uid)
                pipe.incr(vote_count_key)
                pipe.zincrby(vlb_key, 1, sub_id)
                result = await pipe.execute()
                votes = int(result[1])
                return VoteResponse(votes=votes)
            except HTTPException:
                raise
            except Exception:
                continue
            finally:
                await pipe.reset()
