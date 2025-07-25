# Bounty Referral App

This application tracks user referral tasks using FastAPI with a MySQL backend.

## Setup

1. Install requirements
   ```bash
   pip install -r requirements.txt
   ```
2. Configure `DATABASE_URL` in `database.py` and set any API tokens (Telegram, X, Discord, Reddit) as environment variables.
3. Run the application
   ```bash
   uvicorn main:app --reload
   ```
4. Open `http://localhost:8000` in a browser to use the built‑in frontend.

## API Endpoints

- `POST /users` - create a new user
- `POST /tasks/{user_id}` - verify completion of a task and award points

## Submission Guidelines

1. Sign up with the `/users` endpoint by providing a unique `username`, `email` and optional `referral_code`.
2. Use the provided user ID when submitting task completion via `/tasks/{user_id}`.
3. Tasks correspond to actions such as following social profiles or registering a wallet. Each successful verification grants points.
4. Points can be exchanged for rewards once the configured threshold is met. The logic for rewards can be customised in `main.py`.

## Usage Guidelines

* **Run locally** – execute `uvicorn main:app --reload` after installing dependencies. Visit `http://localhost:8000` to use the simple HTML frontend.
* **Environment variables** – provide API tokens for Telegram, X (Twitter), Discord and Reddit. Set `DATABASE_URL` to your MySQL instance.
* **Wallet and newsletter** – register web or mobile wallets via the `/wallets` endpoint and sign up to the mailing list with `/newsletter`.

## Administrator Guidelines

* Ensure a MySQL database is available and update `DATABASE_URL` accordingly. Tables are created automatically on start.
* Create and manage API tokens for third‑party services used by the verification helpers in `utils.py`.
* To modify tasks or reward logic, edit the mappings in `main.py` and the `Task` entries in the database.
