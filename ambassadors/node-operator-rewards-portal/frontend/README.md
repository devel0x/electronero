# Node Operator Rewards Portal Frontend

This lightweight frontend provides the neon-glass UI for the Interchained Node Operator Rewards Portal. It is a static site built with vanilla JavaScript and CSS and communicates with the FastAPI backend.

Accounts flagged as administrators (email present in the backend `PORTAL_ADMIN_EMAILS` list) see an additional control center after logging in. The admin view surfaces pool balances, allows balance/daily payout adjustments, exposes node moderation controls, and can export the current payout cycle as a CSV snapshot.

Admin operators must also unlock the dashboard with the shared portal password. When the backend is configured with
`PORTAL_ADMIN_PORTAL_PASSWORD`, the frontend prompts for it after login and forwards the value via the
`X-Admin-Portal-Key` header on every admin API call.

Both the operator and admin dashboards now display live RPC **and** P2P health indicators so you can confirm that each node is answering bitcoind-style peer handshakes as well as JSON-RPC calls.

## Usage

1. Serve the files from any static web server (e.g. `python -m http.server` inside the `ambassadors/node-operator-rewards-portal/frontend` directory).
2. The app expects the backend to be available at `http://localhost:8000` by default. Override by setting `window.PORTAL_API_URL` before loading `app.js`.

Example using Python's built-in server:

```bash
cd ambassadors/node-operator-rewards-portal/frontend
python -m http.server 9000
```

Then visit `http://localhost:9000` in your browser.
