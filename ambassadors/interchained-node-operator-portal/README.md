# Interchained Node Operator Rewards Portal

This directory contains a full-stack prototype of the Interchained Node Operator
Rewards Portal described in the ambassadors brief. The project is split into a
FastAPI backend powered entirely by Redis (database 6) and a Next.js frontend
with a neon glass aesthetic.

## Backend

* Framework: FastAPI
* Data store: Redis DB 6
* Location: `backend/`

Key features:

* Email + password authentication with bearer token sessions.
* Node registration and CRUD endpoints.
* Background monitor that pings registered nodes every 60 seconds to track
  uptime, responsiveness, and block height.
* Daily reward distribution job that computes payouts based on uptime scores and
  records a per-user history in Redis.

Run locally with:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Set the `REDIS_URL` environment variable if Redis is not available at the
default `redis://localhost:6379/6`.

## Frontend

The frontend is scaffolded with Next.js and TailwindCSS. It provides a neon
inspired operator dashboard including login, node management, uptime metrics,
and reward visualisations.

```
frontend/
├─ pages/
│  ├─ index.js
│  ├─ login.js
│  ├─ dashboard.js
│  ├─ nodes.js
│  └─ rewards.js
├─ components/
│  ├─ NeonCard.js
│  ├─ GlassContainer.js
│  ├─ NodeTable.js
│  ├─ RewardGraph.js
│  └─ StatusBadge.js
└─ styles/
   └─ globals.css
```

Install dependencies and run the dev server:

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the FastAPI backend to be available at
`http://localhost:8000` and uses the same Redis instance configured for the
backend to read metrics and reward data.
