# FastAPI Ambassador Leaderboard

This project is a small FastAPI application that serves an ambassador leaderboard for the Interchained × Elara program. It reads data from a CSV file or a Google Sheet published as CSV, ranks ambassadors by points, and presents both an HTML interface and a JSON API. Pending rewards for each ambassador are calculated by splitting the balance of a configured ITC ambassador pool address in proportion to the ambassadors' points.

The application is protected by an email/password login screen. Only addresses listed in `data/registrations.csv` under the `ambassadors` column may sign in. Users register once to set a password, Telegram username, and wallet address; credentials and profile data are stored in Redis alongside sessions and leaderboard cache data.

Ambassadors can submit links to their social posts for verification, and an admin panel guarded by a password lets administrators review registered emails, wallets, Telegram handles, pending rewards, and submitted posts awaiting verification. Pending posts now show both the submitter's email and a link to their Telegram handle. Verified posts disappear from the queue, and admins may verify or reject each submission. The panel includes navigation links between wallets, posts, and tasks.
Duplicate links are ignored—each ambassador can only submit a given URL once.

A public Raid panel lists every verified post alongside the submitting ambassador's wallet and Telegram handle so the community can coordinate raids. Ambassadors can also redistribute part of their own score to teammates through a dedicated transfer workspace that enforces balance checks, records a per-user ledger, and surfaces every send/receive event in a searchable history table.

The wallet section includes export buttons so administrators can download all ambassadors' scores, pending rewards, wallets, emails, Telegram handles, verification status, weekly activity flags, and verified-post counts as JSON or CSV files. Downloads and reset actions prompt for a password defined in the `GHOST_EXPORT_KEY` environment variable, and a dedicated activity reset button clears weekly activity markers when starting a new reporting cycle.

Admins may also apply a per-user score padding to audit or correct totals without editing the underlying CSV. Padding points are added to the CSV score and reflected in each ambassador's pending reward. The admin panel provides bulk controls to reset padding to zero for selected ambassadors or for all entries at once, and quick "Boost"/"Slash" actions add 1,000 pad points to every active ambassador or zero out pads for inactive users in a single click.

Each ambassador appears in the admin wallet list as a responsive profile card displaying their email, wallet, Telegram handle, padding, pending reward, and badges for both verification and weekly activity. Editing these fields uses asynchronous form submissions so updates apply instantly without reloading the page, and Telegram handles are normalized to lowercase and rendered as clickable links to the user's `t.me` profile.

Administrators also gain new controls and insights:

- **Maintenance mode toggle** – Flip the switch in the admin panel to pause the ambassador-facing dashboard and APIs. Ambassadors receive a dedicated maintenance screen and API calls return HTTP 503 while the toggle is on, but authenticated admins keep full access so back-office work can continue uninterrupted.
- **Visitor analytics dashboard** – The admin landing view now summarizes total and unique visits, surfaces the latest visitor activity (including IP addresses, resolved city/region/country labels, and the most recent path hit), and highlights top locations so admins can spot traffic trends at a glance.
- **User growth chart** – Registration timestamps are aggregated server-side to chart the cumulative number of ambassadors over time, giving admins a quick visual of community growth alongside the tabular analytics cards.
- **Transfer ledger** – Every ambassador-to-ambassador point transfer is streamed into an admin-facing ledger with the source, destination, Telegram handles, timestamps, and amounts so finance and ops teams can audit scorepad movements without querying Redis directly.

## Ambassador transfer workflow

- Visit **Transfers** in the ambassador navigation to open the glassmorphism-styled transfer desk.
- Use the Rolodex search to look up teammates by Telegram handle (with or without `@`), display name, or email. When an entry is missing an email in the CSV, the app backfills it from cached Telegram registrations so every transfer lands on a deliverable address.
- Select a destination from the live-updating results list to populate the transfer form; the panel shows your currently available balance, lifetime sent amount, and lifetime received amount pulled from the Redis-backed ledger.
- Enter an amount up to your available points. Submissions are validated server-side to reject negative numbers, self-transfers, and attempts above the current balance. Successful transfers immediately decrement the sender's score pad, increment the recipient's score pad, and push mirrored `sent`/`received` entries plus a global log for admins.
- Review the on-page history table to confirm the movement. Each row includes direction badges, Telegram shortcuts, and the post-transfer balance snapshot for traceability.

The app also provides a tasks panel where ambassadors can apply to various community roles. Applications are stored in Redis and surface in the admin panel for verification or removal.

### Transfer accounting and running totals

Transfers are persisted in three complementary structures so balances and lifetime totals cannot drift:

1. **Score pad hash** – the authoritative live balance for each ambassador. Every transfer decrements the sender's entry in `score_pad`
   and increments the recipient's entry atomically.
2. **Per-user history lists** – mirrored `sent` and `received` rows stored under `transfers:<email>` provide the timeline shown on the
   dashboard. Each list is trimmed to the most recent `TRANSFER_HISTORY_LIMIT` events to keep rendering fast.
3. **Global log and running totals** – the app also pushes every event into `transfers:global` and increments cumulative counters inside
   `transfers:totals:<email>`. When we introduced the running totals, existing ambassadors could have had more than `TRANSFER_HISTORY_LIMIT`
   entries, which meant the history-based bootstrap alone would undercount them. To avoid that, the application now rebuilds any missing
   `sent` or `received` values by scanning the wider global log exactly once before persisting them. Future transfers simply increment the
   stored counters, so lifetime totals stay accurate even as older history entries fall off the per-user lists.

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
    - Set `GHOST_EXPORT_KEY` to a secret password required for JSON/CSV exports and reset actions.
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
- `GET /transfers` – authenticated transfer panel showing available balance, rolodex search, and personal history.
- `GET /proposals` – list active proposals and submit new ones.
- `GET /raid` – table of verified posts with each submitter's wallet and Telegram handle.
- `POST /proposals/submit` – submit a new proposal (authenticated users).
- `POST /proposals/vote` – vote yes or no on a proposal (authenticated users).
- `POST /transfers` – submit a points transfer to another ambassador (authenticated users; enforces balance checks).
- `GET /api/transfers/rolodex` – JSON rolodex search results for the transfer panel (authenticated users).
- `GET /admin` – password-protected admin panel to view emails, wallets, pending rewards, and posts awaiting verification.
- `POST /admin/proposals/verify` – approve a pending proposal and optionally add a funding wallet (admin).
- `POST /admin/proposals/reject` – reject a pending proposal (admin).
- `POST /tasks/apply` – apply to a task (authenticated users).
- `POST /admin/tasks/verify` – mark a user's task application as verified (admin).
- `POST /admin/tasks/destroy` – remove a user's task application (admin).
- `GET /api/admin/tasks` – JSON dictionary of task applications grouped by user (admin only).
- `GET /api/admin/wallets` – JSON list of all registered emails, wallets, Telegram handles, and pending rewards (admin only).
- `GET /api/admin/posts` – JSON dictionary of submitted posts grouped by user (admin only).
- `POST /admin/scorepad/boost` – add 1,000 pad points to every active ambassador (admin only, requires `GHOST_EXPORT_KEY`).
- `POST /admin/scorepad/slash` – reset pad points to zero for every inactive ambassador (admin only, requires `GHOST_EXPORT_KEY`).
- `GET /api/admin/export?fmt=json|csv&ghost=GHOST` – download scores, pending rewards, wallets, emails, Telegram handles, verification flags, weekly activity status, and verified-post counts (admin only, requires `GHOST_EXPORT_KEY`).
- `POST /admin/activity/reset` – clear weekly activity state for all ambassadors (admin only, requires `GHOST_EXPORT_KEY`).
- Admin reset actions also require the `GHOST_EXPORT_KEY`.

If `AMBASSADOR_POOL_ADDRESS` is set and `interchained-cli` is available, the app tracks the pool's balance and displays each ambassador's pending reward in both the HTML table and the JSON API response.

## Development notes
- Static files are served from `static/` and templates from `templates/`.
- The app caches data for a configurable TTL to limit repeated downloads of the CSV.

## Telegram bot
A companion Telegram bot (`telegram_bot.py`) lets ambassadors interact via chat. Set `TELEGRAM_BOT_TOKEN` in your environment and run the bot to allow ambassadors to register via direct message using `/register <email>` or log in with `/checkin <email>`. Using `/register` in a group triggers a DM prompt; if the bot cannot DM you, it will ask publicly to message @xChiefMod_bot directly. During registration, the bot collects a password, Telegram username, and wallet address. After checking in, ambassadors can update their wallet with `/wallet`.

Use `/hashrate` to query the network's 24‑hour average mining power.

Set `TELEGRAM_ADMIN_IDS` (comma-separated Telegram user IDs) or
`TELEGRAM_ADMIN_USERNAMES` (comma-separated usernames without the leading `@`)
to enable admin-only bot commands. Configured admins can increment an
ambassador's score padding via `/pump @username amount`, which adds to the
existing pad instead of overwriting it—for example, `/pump @interchained 100`
adds 100 points to @interchained's score pad.

