from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


Role = Literal[
    "admin",
    "judge",
    "participant",
    "voter",
    "moderator",
    "auditor",
    "sponsor",
]

SeasonStatus = Literal["draft", "live", "ended", "finalized"]
SubmissionStatus = Literal["pending", "approved", "rejected", "winner"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    role: Role


class LoginResponse(BaseModel):
    uid: str
    token: str
    role: Role


class User(BaseModel):
    uid: str
    username: str
    role: Role
    status: str
    created_at: str


class Season(BaseModel):
    sid: str
    status: SeasonStatus
    created_at: str
    ends_at: Optional[str] = None


class CreateSeasonRequest(BaseModel):
    sid: str = Field(min_length=2, max_length=64)
    status: Optional[SeasonStatus] = None


class SeasonStatusRequest(BaseModel):
    status: SeasonStatus


class SeedJudgesRequest(BaseModel):
    usernames: list[str]


class SubmitRequest(BaseModel):
    threads_url: HttpUrl
    code_phrase: str = Field(min_length=2, max_length=120)


class SubmitResponse(BaseModel):
    sub_id: str


class ModerationRejectRequest(BaseModel):
    reason: Optional[str] = None


class ScoreRequest(BaseModel):
    score: int = Field(ge=0, le=100)
    notes: Optional[str] = None


class VoteResponse(BaseModel):
    votes: int


class FinalizeRequest(BaseModel):
    top_n: int = Field(default=10, ge=1, le=100)


class Submission(BaseModel):
    sub_id: str
    uid: str
    threads_url: str
    code_phrase: str
    status: SubmissionStatus
    created_at: str
    review_notes: Optional[str] = None
    agg_score: Optional[float] = None


class AssignedSubmission(BaseModel):
    sub_id: str
    uid: str
    threads_url: str
    code_phrase: str
    status: SubmissionStatus
    created_at: str
    judge_score: Optional[int] = None
    judge_notes: Optional[str] = None


class LeaderboardEntry(BaseModel):
    sub_id: str
    uid: str
    username: str
    threads_url: str
    status: SubmissionStatus
    score: float


class WinnerEntry(BaseModel):
    sub_id: str
    uid: str
    avg: float


class ApiMessage(BaseModel):
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
