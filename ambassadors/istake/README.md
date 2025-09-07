# IGP Staking Service

This project provides a minimal staking implementation for the Interchained Governance Portal.
Balances, staking positions, points snapshots and reward pools are tracked in Redis while a FastAPI
application exposes user and admin APIs. The service reuses the ambassador leaderboard's
email/password login: user endpoints expect the `session` cookie set by that app and derive the
current email from shared Redis session data.

## Features
- Stake and unstake tokens with configurable lock periods.
- Daily points snapshots and cycle based reward distribution.
- Simple HTML dashboards for public, user and admin views.
- Background workers:
  - **snapshot_worker** – record daily staking points.
  - **reward_cycle_worker** – distribute rewards from funded pools.
  - **expiry_cleaner** – automatically unlock expired positions.

## Running locally
```bash
cd ambassadors/istake
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
The application expects a running Redis instance. Configure the URL via `REDIS_URL` if necessary.

## API endpoints

The service exposes the following HTTP endpoints. All payloads and responses are JSON unless
noted otherwise.

### User

All user endpoints require a valid `session` cookie from the ambassador leaderboard login.

#### `POST /stake`
Create a staking position for the authenticated user.

Payload:

```
{
  "amount": 100,
  "lock_days": 30
}
```

Response:

```
{ "ok": true, "pos_id": 1 }
```

#### `POST /unstake`
Unlock funds after the lock period has passed.

Payload:

```
{
  "pos_id": 1
}
```

Response:

```
{ "ok": true }
```

#### `GET /staking/status`
Query current balances, positions, today's points and accumulated rewards for the logged-in user.

Response:

```
{
  "balances": {"available": 900, "staked": 100, "rewards": 0},
  "positions": [{"pos_id": "1", "amount": 100, ...}],
  "points_today": 110,
  "rewards": 0
}
```

### Admin

#### `POST /staking/pool/fund`
Fund a reward pool for a given cycle.

Payload:

```
{
  "cycle_id": "2024-01",
  "amount": 310
}
```

Response:

```
{ "ok": true }
```

#### `POST /staking/rewards/distribute`
Distribute rewards for a pool based on a daily points snapshot.

Payload:

```
{
  "cycle_id": "2024-01",
  "date": "2024-01-31"
}
```

Response:

```
{ "ok": true, "reward_per_point": 0.1 }
```

### Dashboards

These routes return HTML pages rendered with Jinja templates.

* `GET /` – public landing page.
* `GET /user` – dashboard for the logged-in user.
* `GET /user/{email}` – view another user's dashboard (e.g. admin lookup).
* `GET /admin` – admin dashboard for pool management and reward distribution.
