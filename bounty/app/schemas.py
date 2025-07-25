from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: str
    referral_code: Optional[str] = None

class TaskStatus(BaseModel):
    task_name: str
    completed: bool
    completed_at: Optional[datetime] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    points: int
    class Config:
        orm_mode = True
