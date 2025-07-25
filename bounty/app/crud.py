from sqlalchemy.orm import Session
from . import models, schemas


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(username=user.username, email=user.email, referral_code=user.referral_code)
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

