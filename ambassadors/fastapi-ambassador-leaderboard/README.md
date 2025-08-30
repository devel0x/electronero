# FastAPI Ambassador Leaderboard

This project is a small FastAPI application that serves an ambassador leaderboard for the Interchained × Elara program. It reads data from a CSV file or a Google Sheet published as CSV, ranks ambassadors by points, and presents both an HTML interface and a JSON API. Pending rewards for each ambassador are calculated by splitting the balance of a configured ITC ambassador pool address in proportion to the ambassadors' points.

The application is protected by an email/password login screen. Only addresses listed in `data/registrations.csv` under the `ambassadors` column may sign in. Users register once to set a password, Telegram username, and wallet address; credentials and profile data are stored in Redis alongside sessions and leaderboard cache data.

Ambassadors can submit links to their social posts for verification, and an admin panel guarded by a password lets administrators review registered emails, wallets, Telegram handles, pending rewards, and submitted posts awaiting verification. Verified posts disappear from the queue, and admins may verify or reject each submission. The panel includes navigation links between wallets, posts, and tasks.

The wallet section includes export buttons so administrators can download all ambassadors' scores, pending rewards, wallets, emails, and Telegram handles as JSON or CSV files.

Admins may also apply a per-user score padding to audit or correct totals without editing the underlying CSV. Padding points are added to the CSV score and reflected in each ambassador's pending reward. The admin panel provides bulk controls to reset padding to zero for selected ambassadors or for all entries at once.

The app also provides a tasks panel where ambassadors can apply to various community roles. Applications are stored in Redis and surface in the admin panel for verification or removal.

Ambassadors may submit governance proposals and vote yes or no on active items. Newly submitted proposals remain pending until an administrator approves them in the admin panel, where a funding wallet address can optionally be added. Verified proposals list the original submitter’s wallet as the founder.

## Requirements
- Python 3.11+
- Pinned Python dependencies are listed in `requirements.txt`.
- A running Redis server (configure `REDIS_URL` in `.env`).

## Running locally
1. **Create a virtual environment and install dependencies**
   ```bash
   cd ambassadors/fastapi-ambassador-leaderboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure the data source**
    - Copy `.env` and edit values as needed. By default the app reads `data/leaderboard.csv`.
    - To use a Google Sheet, publish it to CSV and set `SHEET_CSV_URL` in `.env`.
    - Optionally set `AMBASSADOR_POOL_ADDRESS` so the app can fetch the address balance via `interchained-cli` and show pending rewards.
    - Ensure `REGISTRATIONS_CSV` points to a CSV listing authorized ambassador emails.
    - Set `REDIS_URL` if your Redis server differs from the default `redis://localhost:6379/0`.
3. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```
    Visit <http://127.0.0.1:8000>, register your email, password, Telegram username, and wallet address, then log in to view the leaderboard.

## Building
There is no special build step for this app. Installing the dependencies and running the FastAPI server is sufficient. For deployment you can use any ASGI server such as `uvicorn` or `gunicorn` with `uvicorn.workers.UvicornWorker`.

## API endpoints
- `GET /` – HTML leaderboard page.
- `GET /api/leaderboard.json` – JSON representation of the leaderboard. Add `?refresh=true` to bypass cache.
- `GET /health` – simple health check.
- `GET /verify` – page for ambassadors to submit post URLs.
- `GET /tasks` – task checklist for ambassadors with apply buttons.
- `GET /proposals` – list active proposals and submit new ones.
- `POST /proposals/submit` – submit a new proposal (authenticated users).
- `POST /proposals/vote` – vote yes or no on a proposal (authenticated users).
- `GET /admin` – password-protected admin panel to view emails, wallets, pending rewards, and posts awaiting verification.
- `POST /admin/proposals/verify` – approve a pending proposal and optionally add a funding wallet (admin).
- `POST /admin/proposals/reject` – reject a pending proposal (admin).
- `POST /tasks/apply` – apply to a task (authenticated users).
- `POST /admin/tasks/verify` – mark a user's task application as verified (admin).
- `POST /admin/tasks/destroy` – remove a user's task application (admin).
- `GET /api/admin/tasks` – JSON dictionary of task applications grouped by user (admin only).
- `GET /api/admin/wallets` – JSON list of all registered emails, wallets, Telegram handles, and pending rewards (admin only).
- `GET /api/admin/posts` – JSON dictionary of submitted posts grouped by user (admin only).
- `GET /api/admin/export?fmt=json|csv` – download scores, pending rewards, wallets, emails, and Telegram handles (admin only).

If `AMBASSADOR_POOL_ADDRESS` is set and `interchained-cli` is available, the app tracks the pool's balance and displays each ambassador's pending reward in both the HTML table and the JSON API response.

## Development notes
- Static files are served from `static/` and templates from `templates/`.
- The app caches data for a configurable TTL to limit repeated downloads of the CSV.

## Telegram bot
A companion Telegram bot (`telegram_bot.py`) lets ambassadors interact via chat. Set `TELEGRAM_BOT_TOKEN` in your environment and run the bot to allow ambassadors to register via direct message using `/register <email>` or log in with `/checkin <email>`. Using `/register` in a group triggers a DM prompt; if the bot cannot DM you, it will ask publicly to message @xChiefMod_bot directly. During registration, the bot collects a password, Telegram username, and wallet address. After checking in, ambassadors can update their wallet with `/wallet`.

