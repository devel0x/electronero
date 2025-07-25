from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: str
    captcha_token: str
    telegram_handle: str
    twitter_handle: str
    discord_handle: str
    reddit_username: str
    referral_code: Optional[str] = None
    referred_by_id: Optional[int] = None

class TaskStatus(BaseModel):
    task_name: str
    completed: bool
    completed_at: Optional[datetime] = None


class WalletCreate(BaseModel):
    user_id: int
    wallet_type: str
    address: str


class NewsletterCreate(BaseModel):
    email: str


class PayoutAddress(BaseModel):
    user_id: int
    address: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    telegram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    discord_handle: Optional[str] = None
    reddit_username: Optional[str] = None
    points: int
    class Config:
        orm_mode = True

