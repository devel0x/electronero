# FastAPI Ambassador Leaderboard

## Overview
The ambassador leaderboard is a FastAPI application for the Interchained × Elara
program. It ingests community score data from a CSV file (or a Google Sheet
published as CSV), ranks ambassadors, and exposes both a responsive HTML
experience and a JSON API. Pending rewards are computed by splitting the balance
of a configured ITC ambassador pool address across ambassadors according to
their score share.

Authentication uses email and password credentials. Only addresses listed in
`data/registrations.csv` under the `ambassadors` column may sign in. First-time
login collects the ambassador's password, Telegram handle, wallet address,
profile metadata, and KYC questionnaire so the same Redis datastore can hold
sessions, profile state, and compliance submissions. Ambassadors with a pending
or rejected KYC review automatically see a "Complete KYC to become eligible for
payouts" toast on the landing page and within the account settings hub until the
status is verified.

## Feature highlights
### Ambassador experience
- **Leaderboard & raid hub** – Browse rankings, see verified raid posts with
  submitter Telegram handles, and access governance proposals.
- **Account & KYC center** – Update wallet details, profile metadata, compliance
  answers, and upload supporting documents hosted temporarily on
  [temp.sh](https://temp.sh/).
- **Post verification workflow** – Submit promotional links for admin review;
duplicate URLs are automatically rejected.
- **Transfers desk** – Redis-backed ledger and rolodex search let ambassadors
  send or receive points from teammates with full audit history.
- **Tasks & governance** – Apply for community tasks, submit proposals, and vote
  once admins approve them.
- **GameFi arcade** – Slip into the neon `/gamefi` hub to spin the IGP Wheel of
  Fortune, review ledger history, and peek at the upcoming casino lineup.

### Admin experience
- **Wallet operations** – Inline editing of wallets, Telegram handles, and
  profile pads with exports (JSON/CSV) gated by `GHOST_EXPORT_KEY`.
- **KYC review console** – Filter submissions by status, inspect questionnaire
  answers, IP/geolocation context, and document previews, then verify or reject
  without deleting historical records.
- **Analytics dashboard** – Track visitor IPs, geo labels resolved through the
  [ip-api.com](http://ip-api.com) endpoint, and cumulative registrations.
- **Maintenance mode** – Pause ambassador access while keeping admin tools live.
- **Transfer ledger** – Audit every send/receive event, including Telegram
  shortcuts and balance snapshots.
- **GameFi control deck** – Monitor the wheel pool, entry fee, cooldown, and
  slice odds directly from the admin panel with quick links into the ambassador
  arcade.

## Account & KYC center
Ambassadors manage their wallet, profile, and compliance information from the
**Account & KYC Settings** page. Key capabilities include:

- **Profile metadata** – Update display name, preferred social handle, and short
  bio to surface alongside wallet information.
- **Compliance questionnaire** – Capture full legal name, country of residence,
  birthdate, confirmation of being over 18, restricted-region disclosure,
  Politically Exposed Person (PEP) attestation, and optional notes for reviewers.
- **Document uploads** – Identity documents are uploaded directly to
  [temp.sh](https://temp.sh/) using a seven-day `X-Delete-After` header so raw
  files are never persisted on the application server. The temporary URL is
  stored in Redis and previewed to admins.
- **IP and geolocation capture** – Each submission records the source IP and
  fetches a city/region/country label through ip-api. Cached lookups reduce the
  load on the external API.

Submitting KYC data resets the user's status to **Pending**. Badges reflecting
`Pending`, `Verified`, `Rejected`, or `Not Submitted` appear on the wallet cards,
admin dashboard, and payout reminder toast. Ambassadors can resubmit at any time
if details change.

## Admin KYC review workflow
Compliance reviewers work inside the admin dashboard's **KYC** tab:

1. Use the status chips to filter by pending, verified, rejected, or not
   submitted ambassadors.
2. Expand an accordion row to inspect questionnaire answers, IP/geolocation
   context, and the temporary document preview.
3. Approve or reject the submission; status updates propagate to every badge,
   the reminder toast, and the Redis record.
4. Rejected records are retained for auditing and can be revisited when the
   ambassador resubmits.

Wallet cards inside the "Wallets" admin tab also surface the latest KYC badge so
finance and compliance teams see eligibility while preparing payouts.

## Ambassador transfer workflow
- Visit **Transfers** in the ambassador navigation to open the
  glassmorphism-styled transfer desk.
- Use the Rolodex search to look up teammates by Telegram handle (with or
  without `@`), display name, or email. When an entry is missing an email in the
  CSV, cached Telegram registrations backfill the address.
- Select a destination from the live results list to populate the transfer form;
  the panel shows your available balance, lifetime sent amount, and lifetime
  received amount pulled from the Redis-backed ledger.
- Enter an amount up to your available points. Server-side validation blocks
  negative numbers, self-transfers, and attempts above the current balance.
  Successful transfers adjust both score pads immediately and log mirrored
  `sent`/`received` entries plus a global admin audit trail.
- Review the on-page history table to confirm the movement. Each row includes
  direction badges, Telegram shortcuts, and the post-transfer balance snapshot
  for traceability.

## GameFi arcade

### Ambassador view
The `/gamefi` route unlocks a dedicated casino-inspired destination with the
IGP Wheel of Fortune front and centre. Ambassadors can:

- Spin against backend-selected segments that respect Redis locks, pool
  balances, and cooldown timers.
- Track live house metrics (entry fee, bankroll, pool health) alongside a neon
  spin history ticker.
- Preview upcoming drops such as the Mystery Drop Pods and High Roller Matrix
  modes through animated teaser partials.

### Admin control deck
Admins gain a "GameFi" card in the control panel that summarizes:

- Current entry fee, pool balance, cooldown, and the latest wheel status
  message.
- Every configured slice with its multiplier or fixed payout, tone, and weight.
- Recent spin transcripts plus quick configuration hints and a one-click link
  that opens the ambassador-facing arcade in a new tab.

### Configuration & tuning
Wheel odds and state live in Redis so you can tweak them without redeploying:

- `gamefi:wheel:config` – Hash storing `entry_fee`, `pool_balance`,
  `cooldown_seconds`, `enabled`, and a JSON-encoded `segments` list. Update it
  via `redis-cli` or your preferred tooling:

  ```bash
  redis-cli HSET gamefi:wheel:config entry_fee 100 cooldown_seconds 12
  redis-cli HSET gamefi:wheel:config enabled 1 pool_balance 20000
  redis-cli HSET gamefi:wheel:config segments "$(cat segments.json)"
  ```

- `gamefi:wheel:history` – List capturing the most recent spins for auditing and
  surfacing status copy in both the admin deck and ambassador wheel.

After updating the config hash, the next ambassador request automatically picks
up the new values—no process restart required.

## Requirements
- Python 3.11+
- Pinned dependencies listed in `requirements.txt`
- Redis instance (configure `REDIS_URL` in `.env`)
- Outbound internet access so the server can post documents to temp.sh and run
  geolocation lookups via ip-api.com

## Running locally
1. **Create a virtual environment and install dependencies**
   ```bash
   cd ambassadors/fastapi-ambassador-leaderboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure the data source & environment**
   - Copy `.env` and edit values as needed. By default the app reads
     `data/leaderboard.csv`.
   - To use a Google Sheet, publish it to CSV and set `SHEET_CSV_URL`.
   - Optionally set `AMBASSADOR_POOL_ADDRESS` so pending rewards mirror the
     balance returned by `interchained-cli`.
   - Ensure `REGISTRATIONS_CSV` points to a CSV listing authorized ambassador
     emails.
   - Provide `REDIS_URL` if the default `redis://localhost:6379/0` is not
     suitable.
   - Set `GHOST_EXPORT_KEY` to gate admin exports, resets, and bulk actions.
   - Set `ADMIN_PASSWORD` to protect the admin dashboard and KYC review tools.
   - Configure `INTERCHAINED_CLI`, `CLI_EXTRA`, and `RPC_WALLET` if the app needs
     to query a remote Interchained node.
3. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```
   Visit <http://127.0.0.1:8000> to register, update your profile, submit KYC,
   and view the leaderboard.

## Building
No special build step is required. Installing dependencies and running an ASGI
server such as `uvicorn` or `gunicorn` with
`uvicorn.workers.UvicornWorker` is sufficient for deployment.

## API endpoints
- `GET /` – HTML leaderboard page.
- `GET /gamefi` – Neon casino hub with the IGP Wheel of Fortune (authenticated).
- `GET /api/leaderboard.json` – JSON leaderboard (add `?refresh=true` to bypass
  cache).
- `GET /api/gamefi/wheel/state` – Current wheel entry fee, pool, and slice
  configuration (authenticated).
- `POST /api/gamefi/wheel/spin` – Atomically deduct the entry fee, resolve a
  slice, and log the spin (authenticated).
- `GET /health` – Basic health check.
- `GET /verify` – Submit social posts for verification.
- `GET /tasks` – Task checklist with application forms.
- `GET /transfers` – Authenticated transfer panel showing balances and history.
- `GET /proposals` – List and submit governance proposals.
- `GET /raid` – Table of verified posts with submitter wallet and Telegram
  handle.
- `POST /proposals/submit` – Submit a new proposal (authenticated).
- `POST /proposals/vote` – Vote on a proposal (authenticated).
- `POST /transfers` – Send points to another ambassador (authenticated).
- `GET /api/transfers/rolodex` – JSON rolodex search results (authenticated).
- `GET /admin` – Password-protected admin panel with wallets, posts, tasks, and
  analytics.
- `POST /admin/proposals/verify` – Approve a pending proposal (admin).
- `POST /admin/proposals/reject` – Reject a pending proposal (admin).
- `POST /tasks/apply` – Submit a task application (authenticated).
- `POST /admin/tasks/verify` – Mark a user's task application as verified
  (admin).
- `POST /admin/tasks/destroy` – Remove a user's task application (admin).
- `GET /api/admin/tasks` – JSON dictionary of task applications (admin).
- `GET /api/admin/wallets` – JSON list of ambassador wallets, Telegram handles,
  pending rewards, and KYC status (admin).
- `GET /api/admin/posts` – JSON dictionary of submitted posts (admin).
- `POST /admin/scorepad/boost` – Add 1,000 pad points to every active ambassador
  (admin; requires `GHOST_EXPORT_KEY`).
- `POST /admin/scorepad/slash` – Reset pad points to zero for inactive
  ambassadors (admin; requires `GHOST_EXPORT_KEY`).
- `GET /api/admin/export?fmt=json|csv&ghost=GHOST` – Download ambassadors' data
  as JSON or CSV (admin; requires `GHOST_EXPORT_KEY`).
- `POST /admin/activity/reset` – Clear weekly activity state (admin; requires
  `GHOST_EXPORT_KEY`).

If `AMBASSADOR_POOL_ADDRESS` is set and `interchained-cli` is available, the app
tracks the pool balance and displays each ambassador's pending reward in both
the HTML table and JSON response.

## Development notes
- Static assets live in `static/`, templates in `templates/`.
- Redis caches leaderboard data, analytics, and geolocation lookups with a
  configurable TTL.

## Telegram bot
A companion Telegram bot (`telegram_bot.py`) lets ambassadors interact via chat.
Set `TELEGRAM_BOT_TOKEN` and run the bot to allow ambassadors to register via
`/register <email>` or log in with `/checkin <email>`. Using `/register` in a
public group triggers a DM prompt; if the bot cannot message the user, it asks
them to contact @xChiefMod_bot directly. Registration collects a password,
Telegram username, and wallet address. After checking in, ambassadors can update
their wallet with `/wallet`.

Admins can define `TELEGRAM_ADMIN_IDS` (comma-separated user IDs) or
`TELEGRAM_ADMIN_USERNAMES` (comma-separated handles without `@`) to unlock
bot-only commands. Approved admins may add score padding with
`/pump @username amount`, which increments the existing pad (for example,
`/pump @interchained 100`). Use `/hashrate` to query the network's 24-hour
average mining power.
