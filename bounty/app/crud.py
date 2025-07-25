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
