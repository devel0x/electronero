from sqlalchemy.orm import Session
import secrets
from . import models, schemas


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


def claim_reward(db: Session, user_id: int, threshold: int, rate: float):
    user = get_user(db, user_id)
    if not user or user.points < threshold:
        return None
    reward_itc = user.points * rate
    claim = models.RewardClaim(
        user_id=user_id, points=user.points, reward_itc=reward_itc
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

