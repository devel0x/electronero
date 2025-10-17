# Interchained Node Operator Rewards Portal

This FastAPI application powers a neon-themed operations portal for Bitcoin node
operators. Operators register their nodes via Redis (database 6) and the portal
continuously verifies health, tracks uptime, and estimates daily reward shares
from a shared mining pool.

## Features

- Async Redis integration scoped to database 6 with key namespace `node:{email}`
- Periodic `getblockchaininfo` health checks via JSON-RPC to verify node
  responsiveness, best block height, and uptime accumulation
- Neon glassmorphism UI with secure login gate, daily pool controls, and payout
  preview tables
- Reward weight calculator that proportionally splits the configured reward pool
  based on measured uptime

## Running locally

1. Ensure Redis is running and accessible (`redis://localhost:6379/6` by
   default).
2. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r node_portal/requirements.txt
   ```

3. Provision an operator account:

   ```bash
   uvicorn node_portal.app.main:app --reload
   curl -X POST http://localhost:8000/api/users \
     -H 'Content-Type: application/json' \
     -d '{"email": "satoshi@bitcoin.org", "password": "super-secret"}'
   ```

4. Login at <http://localhost:8000/login> and register node metadata using the
   `/nodes` endpoint or direct Redis writes. The background scheduler will
   automatically begin health checks and update uptime metrics.

## Key Redis structures

| Key pattern                 | Type  | Description                                    |
|-----------------------------|-------|------------------------------------------------|
| `node:{email}`              | Hash  | Node metadata (`node_address`, `p2p_port`, `rpc_port`, `wallet_address`) |
| `metrics:{email}`           | Hash  | Derived metrics (`uptime_seconds`, `last_block_height`, `last_checked`) |
| `nodes:active` / `inactive` | Set   | Maintains active/inactive classification        |
| `pool:daily_reward`         | Value | Current daily reward pool in BTC               |
| `user:{email}`              | Hash  | Portal login credentials (bcrypt hashed)       |

The `/api/payouts` endpoint exposes the JSON summary used by the dashboard.
