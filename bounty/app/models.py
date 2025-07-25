from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    referral_code = Column(String(20), unique=True, index=True)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), unique=True, index=True)
    wallet_address = Column(String(100), nullable=True)
    telegram_handle = Column(String(100), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    discord_handle = Column(String(100), nullable=True)
    reddit_username = Column(String(100), nullable=True)
    points = Column(Integer, default=0)

    referrals = relationship("User", remote_side=[id])
    tasks = relationship("UserTask", back_populates="user")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True)
    points = Column(Integer, default=0)

class UserTask(Base):
    __tablename__ = "user_tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    task = relationship("Task")


class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    wallet_type = Column(String(20))
    address = Column(String(100))


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True)


class RewardClaim(Base):
    __tablename__ = "reward_claims"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    points = Column(Integer)
    reward_itc = Column(Float)
    claimed_at = Column(DateTime, default=datetime.utcnow)

