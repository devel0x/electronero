from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from . import models, schemas, crud, utils

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Referral Bounty App")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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

