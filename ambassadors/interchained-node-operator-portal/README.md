# Interchained Operator Control Plane

An enterprise-grade SaaS portal for managing Interchained node operators. The
platform combines a FastAPI backend, Redis DB 6 telemetry store, and a Next.js
frontend to deliver RBAC, analytics, automated rewards, and compliance tooling
for distributed infrastructure teams.

## Backend

* Framework: FastAPI
* Data store: Redis DB 6
* Location: `backend/`

### Highlights

* **Multi-tenant RBAC** – Super admins provision organisations, org admins manage
  operators/auditors through invite workflows, and all access is tokenised.
* **Node lifecycle management** – Register, tag, and flag nodes per
  organisation. Background monitors capture uptime, latency, and block height
  every 60 seconds.
* **Reward distribution** – Daily payouts weight uptime scores with service plan
  multipliers and persist organisation-level history plus lifetime accruals.
* **Analytics & billing** – API endpoints expose fleet metrics (MRR, plan
  distribution, uptime trends) and tenant billing summaries.
* **Audit logging** – Immutable audit events for invitations, role updates,
  organisation changes, and node flagging.

### Running locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Set `PORTAL_REDIS_URL` if Redis is not running at `redis://localhost:6379/6`.

## Frontend

* Framework: Next.js + TailwindCSS
* Location: `frontend/`

### Key screens

```
frontend/
├─ pages/
│  ├─ index.js            # Marketing / landing
│  ├─ login.js            # Auth & invite flow
│  ├─ dashboard.js        # Executive overview
│  ├─ nodes.js            # Node inventory & provisioning
│  ├─ rewards.js          # Reward analytics
│  └─ admin/
│     ├─ audit.js         # Audit trail browser
│     ├─ billing.js       # Billing summary
│     ├─ organizations.js # Super-admin tenant management
│     └─ users.js         # Team access & invites
├─ components/
│  ├─ layout/AdminShell.js
│  ├─ navigation/SidebarNav.js
│  ├─ cards/MetricCard.js
│  ├─ charts/UptimeTrend.js
│  ├─ tables/AuditTable.js
│  ├─ tables/OrganizationTable.js
│  ├─ NodeTable.js
│  └─ RewardGraph.js
└─ lib/api.js
```

### Running locally

```bash
cd frontend
npm install
npm run dev
```

The frontend targets `http://localhost:8000/api/v1` by default. Override with
`NEXT_PUBLIC_API_BASE` when deploying. Both tiers share the same Redis instance
for telemetry and session storage.

## Architectural Notes

* **Lifespan-managed services** – `NodeMonitor` and `RewardDistributor` start
  and stop with FastAPI, ensuring clean shutdown of background tasks.
* **Analytics service layer** – `services/analytics.py` aggregates plan
  distribution, uptime averages, and billing information for dashboards.
* **Storage layout** – Redis hashes and sets are namespaced per organisation
  (`org:{id}:*`) to simplify tenant isolation and analytics fan-out.
* **Frontend auth context** – `AuthProvider` persists bearer sessions, injects
  tokens into API calls, and gates protected routes via `AdminShell`.

