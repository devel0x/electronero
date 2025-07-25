from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from . import models, schemas, crud, utils
import os

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Referral Bounty App")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
REWARD_THRESHOLD = int(os.getenv("REWARD_THRESHOLD", "100"))

# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    links = {
        "telegram": os.getenv("TELEGRAM_URL", "#"),
        "x_profile": os.getenv("X_PROFILE_URL", "#"),
        "discord": os.getenv("DISCORD_URL", "#"),
        "web_wallet": os.getenv("WEB_WALLET_URL", "#"),
        "mobile_wallet": os.getenv("MOBILE_WALLET_URL", "#"),
        "newsletter": os.getenv("NEWSLETTER_URL", "#"),
        "reddit": os.getenv("REDDIT_URL", "#"),
        "tweet": os.getenv("TWEET_URL", "#"),
        "referral_base": os.getenv("REFERRAL_BASE_URL", "")
    }
    return templates.TemplateResponse(
        "index.html", {"request": request, "links": links}
    )

@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    return crud.create_user(db, user)

@app.post("/tasks/{user_id}")
def complete_task(user_id: int, status: schemas.TaskStatus, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    verification_map = {
        "telegram": lambda: utils.verify_telegram(user.username),
        "x": lambda: utils.verify_x_handle(user.username),
        "discord": lambda: utils.verify_discord(user.username),
        "web_wallet": lambda: utils.verify_wallet(db, user.id, "web"),
        "mobile_wallet": lambda: utils.verify_wallet(db, user.id, "mobile"),
        "newsletter": lambda: utils.verify_newsletter(db, user.email),
        "reddit": lambda: utils.verify_reddit(user.username),
        "tweet": lambda: utils.verify_tweet(user.username),
    }

    verifier = verification_map.get(status.task_name)
    if not verifier:
        raise HTTPException(status_code=400, detail="Unknown task")

    if verifier():
        crud.add_points(db, user_id, 10)
        return {"message": "Task completed"}

    raise HTTPException(status_code=400, detail="Verification failed")


@app.post("/wallets")
def register_wallet(wallet: schemas.WalletCreate, db: Session = Depends(get_db)):
    record = crud.register_wallet(db, wallet.user_id, wallet.wallet_type, wallet.address)
    if not record:
        raise HTTPException(status_code=400, detail="Wallet already registered")
    return {"message": "Wallet registered"}


@app.post("/newsletter")
def subscribe_newsletter(data: schemas.NewsletterCreate, db: Session = Depends(get_db)):
    record = crud.add_newsletter(db, data.email)
    if not record:
        raise HTTPException(status_code=400, detail="Already subscribed")
    return {"message": "Subscribed"}


@app.post("/claim/{user_id}")
def claim_reward(user_id: int, db: Session = Depends(get_db)):
    claim = crud.claim_reward(db, user_id, REWARD_THRESHOLD)
    if not claim:
        raise HTTPException(status_code=400, detail="Not enough points to claim")
    return {"message": "Reward claimed", "points": claim.points, "claimed_at": claim.claimed_at}

