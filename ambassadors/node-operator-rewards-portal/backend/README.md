# Node Operator Rewards Portal Backend

This FastAPI application powers the Interchained Node Operator Rewards Portal. It keeps track of registered nodes, monitors their health and responsiveness, and distributes daily rewards proportionally to performance.

## Features

- JWT-secured authentication endpoints for node operators.
- Node registration and management API.
- Background health monitoring that pings node RPC endpoints every 60 seconds.
- Redis-backed storage for users, nodes, uptime metrics, and reward history.
- Reward engine that performs daily weighted distributions and flags high-performing nodes.
- Administrative APIs for managing the reward pool balance, adjusting daily payouts, moderating nodes, and exporting payout
  snapshots.

## Requirements

- Python 3.11+
- Redis server (DB 6 is used by default)

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file with the following minimum configuration:

```env
PORTAL_SECRET_KEY="<32+ character random string>"
PORTAL_REDIS_URL="redis://localhost:6379/6"
PORTAL_REWARD_POOL_DAILY=1000
PORTAL_INITIAL_POOL_BALANCE=100000
PORTAL_ADMIN_EMAILS="admin@example.com,finance@example.com"
```

Run the development server:

```bash
uvicorn app.main:app --reload
```

The API documentation is available at `http://localhost:8000/docs` once the server is running.

### Admin access

Any account whose email matches one of the `PORTAL_ADMIN_EMAILS` entries is granted administrative access after registration.
Admin tokens expose the following additional routes:

- `GET /admin/pool` – Inspect the live pool balance, daily distribution amount, and recent payout metadata.
- `POST /admin/pool/adjust` – Deposit or withdraw funds from the pool balance.
- `PUT /admin/pool/daily` – Update the daily payout amount used by the reward engine.
- `GET /admin/nodes` – Review all registered nodes including uptime metrics and owner contact emails.
- `POST /admin/nodes/{id}/reject` / `POST /admin/nodes/{id}/reinstate` – Toggle node eligibility for payouts.
- `GET /admin/exports/payouts` – Generate a CSV-friendly snapshot of the current payout cycle (node, wallet, share).
