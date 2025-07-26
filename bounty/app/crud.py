from sqlalchemy.orm import Session
import secrets
import subprocess
import os
from passlib.context import CryptContext
from . import models, schemas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _generate_referral_code(db: Session) -> str:
    """Return a unique referral code."""
    while True:
        code = secrets.token_hex(4)
        if not db.query(models.User).filter(models.User.referral_code == code).first():
            return code


def create_user(db: Session, user: schemas.UserCreate, ip_address: str) -> models.User | None:
    if db.query(models.User).filter(models.User.email == user.email).first():
        return None
    if db.query(models.User).filter(models.User.ip_address == ip_address).first():
        return None
    code = user.referral_code or _generate_referral_code(db)
    db_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=pwd_context.hash(user.password),
        telegram_handle=user.telegram_handle,
        twitter_handle=user.twitter_handle,
        discord_handle=user.discord_handle,
        reddit_username=user.reddit_username,
        wallet_address=user.wallet_address,
        referral_code=code,
        referred_by_id=user.referred_by_id,
        ip_address=ip_address,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def authenticate_user(db: Session, username: str, password: str) -> models.User | None:
    user = db.query(models.User).filter(models.User.username == username).first()
    if user and pwd_context.verify(password, user.password_hash):
        return user
    return None

def add_points(db: Session, user_id: int, points: int):
    user = get_user(db, user_id)
    if user:
        user.points += points
        db.commit()
    return user


def wallet_registered(db: Session, user_id: int, wallet_type: str) -> bool:
    return (
        db.query(models.Wallet)
        .filter(models.Wallet.user_id == user_id, models.Wallet.wallet_type == wallet_type)
        .first()
        is not None
    )


def register_wallet(db: Session, user_id: int, wallet_type: str, address: str):
    if not wallet_registered(db, user_id, wallet_type):
        record = models.Wallet(user_id=user_id, wallet_type=wallet_type, address=address)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    return None


def newsletter_subscribed(db: Session, email: str) -> bool:
    return db.query(models.NewsletterSubscriber).filter(models.NewsletterSubscriber.email == email).first() is not None


def add_newsletter(db: Session, email: str):
    if not newsletter_subscribed(db, email):
        sub = models.NewsletterSubscriber(email=email)
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub
    return None


def _get_or_create_task(db: Session, name: str, pts: int) -> models.Task:
    task = db.query(models.Task).filter(models.Task.name == name).first()
    if not task:
        task = models.Task(name=name, points=pts)
        db.add(task)
        db.commit()
        db.refresh(task)
    return task


def complete_task(db: Session, user_id: int, task_name: str, pts: int) -> bool:
    """Mark a task as completed and award points if not already done."""
    task = _get_or_create_task(db, task_name, pts)
    existing = (
        db.query(models.UserTask)
        .filter(models.UserTask.user_id == user_id, models.UserTask.task_id == task.id)
        .first()
    )
    if existing:
        return False
    record = models.UserTask(user_id=user_id, task_id=task.id, completed=True)
    db.add(record)
    add_points(db, user_id, pts)
    db.commit()
    return True


def get_completed_tasks(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(models.Task.name)
        .join(models.UserTask, models.UserTask.task_id == models.Task.id)
        .filter(models.UserTask.user_id == user_id, models.UserTask.completed == True)
        .all()
    )
    return [r.name for r in rows]


def count_referrals(db: Session, user_id: int) -> int:
    """Return how many other users were referred by the given user."""
    return db.query(models.User).filter(models.User.referred_by_id == user_id).count()


def claim_reward(db: Session, user_id: int, threshold: int, rate: float, refs: int = 0):
    """Claim rewards using current points plus referral bonus."""
    user = get_user(db, user_id)
    if not user or user.points < threshold:
        return None
    total_points = int(user.points * (1 + (refs * 0.01)))
    reward_itc = total_points * rate
    claim = models.RewardClaim(
        user_id=user_id, points=total_points, reward_itc=reward_itc
    )
    user.points = 0
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def set_payout_address(db: Session, user_id: int, address: str) -> models.User | None:
    user = get_user(db, user_id)
    if not user:
        return None
    user.wallet_address = address
    db.commit()
    db.refresh(user)
    return user


def process_reward_claim(db: Session, claim_id: int, cli_path: str | None = None):
    """Send payment using interchained-cli and record the txid."""
    claim = db.query(models.RewardClaim).filter(models.RewardClaim.id == claim_id).first()
    if not claim or claim.txid:
        return None
    user = get_user(db, claim.user_id)
    if not user or not user.wallet_address:
        return None
    cli = cli_path or os.getenv("INTERCHAINED_CLI", "interchained-cli")
    result = subprocess.run(
        [cli, "sendToAddress", user.wallet_address, str(claim.reward_itc)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    claim.txid = result.stdout.strip()
    db.commit()
    db.refresh(claim)
    return claim

