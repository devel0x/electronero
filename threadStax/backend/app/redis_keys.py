from .config import settings


PREFIX = settings.redis_key_prefix


def user(uid: str) -> str:
    return f"{PREFIX}u:{uid}"


def role_set(role: str) -> str:
    return f"{PREFIX}role:{role}"


def session(token: str) -> str:
    return f"{PREFIX}sess:{token}"


def season(sid: str) -> str:
    return f"{PREFIX}season:{sid}"


def seasons() -> str:
    return f"{PREFIX}seasons"


def submission(sid: str, sub_id: str) -> str:
    return f"{PREFIX}s:{sid}:{sub_id}"


def submissions(sid: str) -> str:
    return f"{PREFIX}subs:{sid}"


def user_submissions(uid: str, sid: str) -> str:
    return f"{PREFIX}u:{uid}:subs:{sid}"


def moderation_queue(sid: str) -> str:
    return f"{PREFIX}queue:mod:{sid}"


def flag(sid: str, sub_id: str) -> str:
    return f"{PREFIX}flag:{sid}:{sub_id}"


def judge_assigned(sid: str, judge_uid: str) -> str:
    return f"{PREFIX}judge:{sid}:{judge_uid}:assigned"


def score(sid: str, sub_id: str, judge_uid: str) -> str:
    return f"{PREFIX}score:{sid}:{sub_id}:{judge_uid}"


def score_agg(sid: str, sub_id: str) -> str:
    return f"{PREFIX}score:{sid}:{sub_id}:agg"


def leaderboard(sid: str) -> str:
    return f"{PREFIX}lb:{sid}"


def vote_set(sid: str, sub_id: str) -> str:
    return f"{PREFIX}vote:{sid}:{sub_id}"


def vote_count(sid: str, sub_id: str) -> str:
    return f"{PREFIX}vote:{sid}:{sub_id}:count"


def vote_leaderboard(sid: str) -> str:
    return f"{PREFIX}vlb:{sid}"


def payout(sid: str, uid: str) -> str:
    return f"{PREFIX}payout:{sid}:{uid}"


def payout_queue(sid: str) -> str:
    return f"{PREFIX}queue:payout:{sid}"


def rate_limit_submit(uid: str, sid: str) -> str:
    return f"{PREFIX}rl:submit:{uid}:{sid}"


def rate_limit_vote(uid: str, sid: str) -> str:
    return f"{PREFIX}rl:vote:{uid}:{sid}"
