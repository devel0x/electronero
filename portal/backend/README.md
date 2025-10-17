# Node Operator Rewards Portal Backend

This FastAPI application powers the Interchained Node Operator Rewards Portal. It keeps track of registered nodes, monitors their health and responsiveness, and distributes daily rewards proportionally to performance.

## Features

- JWT-secured authentication endpoints for node operators.
- Node registration and management API.
- Background health monitoring that pings node RPC endpoints every 60 seconds.
- Redis-backed storage for users, nodes, uptime metrics, and reward history.
- Reward engine that performs daily weighted distributions and flags high-performing nodes.

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
```

Run the development server:

```bash
uvicorn app.main:app --reload
```

The API documentation is available at `http://localhost:8000/docs` once the server is running.
