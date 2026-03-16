# IGP Staking Service

This project provides a minimal staking implementation for the Interchained Governance Portal.  
Balances, staking positions, points snapshots and reward pools are tracked in Redis while a FastAPI
application exposes user and admin APIs.

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
- `POST /stake` – create a staking position for a user.
- `POST /unstake` – unlock funds after the lock period.
- `GET /staking/status/{email}` – query balances, positions, points and rewards.
- `POST /staking/pool/fund` – add funds to a reward pool (admin).
- `POST /staking/rewards/distribute` – distribute pool rewards based on points (admin).
