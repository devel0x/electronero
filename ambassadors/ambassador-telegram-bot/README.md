# Ambassador Telegram Bot

This bot provides a Telegram interface to the Ambassador program.
It uses the FastAPI application's JSON APIs and Redis data to let
ambassadors check in, view the leaderboard, see task status and submit
posts.

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   cd ambassadors/ambassador-telegram-bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Create a `.env` file with:
   ```dotenv
   TELEGRAM_BOT_TOKEN="<bot token>"
   REDIS_URL="redis://localhost:6379/0"
   AMBASSADOR_API_BASE="http://localhost:8000"
   ```
3. Run the bot:
   ```bash
   python bot.py
   ```

## Commands

- `/checkin` – verify your Telegram handle against registrations
- `/leaderboard` – show top ambassadors using the public API
- `/tasks` – list available tasks and your application status
- `/apply <task>` – apply for a task
- `/submit <url>` – submit a post URL for verification

The bot reuses the same Redis instance as the FastAPI app, so your
registrations and submissions stay in sync.
