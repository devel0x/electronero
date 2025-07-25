# Bounty Referral App

This is a minimal FastAPI application using MySQL to manage user referral tasks.

## Setup

1. Install requirements
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the database URL in `database.py`.

3. Run the application
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints

- `POST /users` - create a new user
- `POST /tasks/{user_id}` - verify completion of a task and award points
