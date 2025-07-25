from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from .database import SessionLocal, engine
from . import models, schemas, crud, utils
from .translations import translations
import os

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Referral Bounty App")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
REWARD_THRESHOLD = int(os.getenv("REWARD_THRESHOLD", "100"))
ITC_PER_POINT = float(os.getenv("ITC_PER_POINT", "0.01"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SERVER_PORT = os.getenv("SERVER_PORT", "8000")
security = HTTPBasic()
user_security = HTTPBasic()

# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    user_id: int, credentials: HTTPBasicCredentials = Depends(user_security), db: Session = Depends(get_db)
) -> models.User:
    user = crud.authenticate_user(db, credentials.username, credentials.password)
    if not user or user.id != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


@app.get("/", response_class=HTMLResponse)
def index(request: Request, lang: str | None = None):
    server_port = SERVER_PORT
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
    language = lang or os.getenv("DEFAULT_LANGUAGE", "en")
    strings = translations.get(language, translations["en"])
    return templates.TemplateResponse(
        "index.html", {"request": request, "links": links, "t": strings, "server_port": SERVER_PORT}
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, lang: str | None = None):
    language = lang or os.getenv("DEFAULT_LANGUAGE", "en")
    strings = translations.get(language, translations["en"])
    return templates.TemplateResponse("register.html", {"request": request, "t": strings, "server_port": SERVER_PORT})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, lang: str | None = None):
    language = lang or os.getenv("DEFAULT_LANGUAGE", "en")
    strings = translations.get(language, translations["en"])
    return templates.TemplateResponse("login.html", {"request": request, "t": strings, "server_port": SERVER_PORT})


@app.post("/login")
def login(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"user_id": user.id, "server_port": SERVER_PORT}

@app.post("/users", response_model=schemas.UserResponse)
def create_user(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    if not utils.verify_captcha(user.captcha_token):
        raise HTTPException(status_code=400, detail="CAPTCHA failed")
    ip = request.headers.get("X-Forwarded-For", request.client.host)
    db_user = crud.create_user(db, user, ip)
    if not db_user:
        raise HTTPException(status_code=400, detail="User already registered")
    return db_user

@app.post("/tasks/{user_id}")
def complete_task(
    user_id: int,
    status: schemas.TaskStatus,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user = current_user

    verification_map = {
        "telegram": lambda: utils.verify_telegram(user.telegram_handle),
        "x": lambda: utils.verify_x_handle(user.twitter_handle),
        "discord": lambda: utils.verify_discord(user.discord_handle),
        "web_wallet": lambda: utils.verify_wallet(db, user.id, "web"),
        "mobile_wallet": lambda: utils.verify_wallet(db, user.id, "mobile"),
        "newsletter": lambda: utils.verify_newsletter(db, user.email),
        "reddit": lambda: utils.verify_reddit(user.reddit_username),
        "tweet": lambda: utils.verify_tweet(user.twitter_handle),
    }

    verifier = verification_map.get(status.task_name)
    if not verifier:
        raise HTTPException(status_code=400, detail="Unknown task")

    if verifier():
        if crud.complete_task(db, user_id, status.task_name, 10):
            return {"message": "Task completed"}
        raise HTTPException(status_code=400, detail="Task already completed")

    raise HTTPException(status_code=400, detail="Verification failed")


@app.post("/wallets")
def register_wallet(
    wallet: schemas.WalletCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id != wallet.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
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


@app.post("/payout_address")
def add_payout_address(
    data: schemas.PayoutAddress,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id != data.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = crud.set_payout_address(db, data.user_id, data.address)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Wallet address saved"}


@app.post("/claim/{user_id}")
def claim_reward(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    claim = crud.claim_reward(db, user_id, REWARD_THRESHOLD, ITC_PER_POINT)
    if not claim:
        raise HTTPException(status_code=400, detail="Not enough points to claim")
    return {
        "message": "Reward claimed",
        "points": claim.points,
        "reward_itc": claim.reward_itc,
        "claimed_at": claim.claimed_at,
    }


@app.get("/progress/{user_id}")
def get_progress(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tasks = crud.get_completed_tasks(db, user_id)
    return {"points": current_user.points, "completed_tasks": tasks}


@app.post("/process_claim/{claim_id}")
def process_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = crud.process_reward_claim(db, claim_id)
    if not claim:
        raise HTTPException(status_code=400, detail="Unable to process claim")
    return {"message": "Payment sent", "txid": claim.txid}


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not secrets.compare_digest(credentials.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Unauthorized")
    users = db.query(models.User).all()

    Ref = aliased(models.User)
    referral_rows = (
        db.query(models.User.id, func.count(Ref.id).label("cnt"))
        .outerjoin(Ref, Ref.referred_by_id == models.User.id)
        .group_by(models.User.id)
        .all()
    )
    referral_counts = {row.id: row.cnt for row in referral_rows}

    task_rows = (
        db.query(models.UserTask.user_id, func.count(models.UserTask.id).label("cnt"))
        .filter(models.UserTask.completed == True)
        .group_by(models.UserTask.user_id)
        .all()
    )
    task_counts = {row.user_id: row.cnt for row in task_rows}

    claims = db.query(models.RewardClaim).order_by(models.RewardClaim.claimed_at.desc()).all()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "users": users,
            "claims": claims,
            "referral_counts": referral_counts,
            "task_counts": task_counts,
        },
    )


@app.get("/analytics/leaderboard")
def referral_leaderboard(db: Session = Depends(get_db)):
    Ref = aliased(models.User)
    results = (
        db.query(models.User.id, models.User.username, func.count(Ref.id).label("refs"))
        .outerjoin(Ref, Ref.referred_by_id == models.User.id)
        .group_by(models.User.id)
        .order_by(func.count(Ref.id).desc())
        .limit(10)
        .all()
    )
    return [
        {"user_id": r.id, "username": r.username, "referrals": r.refs}
        for r in results
    ]

