from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from . import models, schemas, crud, utils

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Referral Bounty App")

# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    return crud.create_user(db, user)

@app.post("/tasks/{user_id}")
def complete_task(user_id: int, status: schemas.TaskStatus, db: Session = Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    verification_map = {
        "telegram": utils.verify_telegram,
        "x": utils.verify_x_handle,
        "discord": utils.verify_discord,
        "web_wallet": utils.verify_wallet,
        "mobile_wallet": utils.verify_wallet,
        "newsletter": utils.verify_newsletter,
        "reddit": utils.verify_reddit,
        "tweet": utils.verify_tweet,
    }

    verifier = verification_map.get(status.task_name)
    if not verifier:
        raise HTTPException(status_code=400, detail="Unknown task")

    if verifier(status.task_name):
        # In a real app you'd map the task_name to a Task entry in DB
        crud.add_points(db, user_id, 10)
        return {"message": "Task completed"}
    raise HTTPException(status_code=400, detail="Verification failed")
