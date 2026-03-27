# Telegram Ambassador Bot

This bot mirrors basic functionality from the FastAPI ambassador
application and interacts with its HTTP APIs.

## Features
- **Email/password check‑in**: users authenticate against the FastAPI login endpoint and link their Telegram ID to the account. Check-ins must be done in a private chat with the bot.
- **Leaderboard lookup** using `/api/leaderboard.json`.
- **Task list** mirroring the web application.
- **Task application** forwarded to the FastAPI `/tasks/apply` endpoint.
- **Post verification** – submit links with `/verify <url>` for admins to review.

## Usage
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Export required environment variables:
   - `TELEGRAM_BOT_TOKEN` – token obtained from BotFather.
   - `AMBASSADOR_API_BASE_URL` – base URL of the ambassador FastAPI service (defaults to `http://localhost:8000`).
3. Run the bot:
   ```bash
   python bot.py
   ```
   Use `/checkin <email>` in a direct message to the bot and reply with your password when prompted.
   - `/verify <url>` submits a post for admin verification.

User mappings are stored in `data/telegram_users.json` and include a session token from the API.
