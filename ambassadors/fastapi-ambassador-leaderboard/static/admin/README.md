# Ambassador Admin React SPA

This directory contains the static assets that power the Ambassador admin dashboard. The panel is a small React single-page application that is served directly by FastAPI from `/static/admin/index.html` and enhanced by the `app.js` bundle. The goal of the rewrite was to significantly reduce the time-to-interaction for admins while giving parity (and improvements) over the legacy server-rendered templates.

## Project layout

- `index.html` – HTML shell that mounts the React app and loads the ESM bundles from `app.js` and `styles.css`.
- `app.js` – The React entry point. It fetches the consolidated `/api/admin/dashboard` snapshot and orchestrates all feature-specific components (analytics, wallets, moderation, scorepad activity, transfers, proposals, recoveries, and maintenance tools).
- `styles.css` – Dashboard-specific styling layered on top of Bootstrap. Styling is intentionally isolated here so that the rest of the FastAPI site can continue using the existing global styles.

Because the app is entirely client-rendered and uses ESM imports from CDNs (via `https://esm.sh/`), no build step or Node.js toolchain is required—FastAPI serves the raw files as-is.

## Data flow and backend contracts

The SPA communicates with a set of JSON endpoints that live in `main.py`:

- `GET /api/admin/dashboard` returns the aggregated snapshot used to paint the overview cards and tables.
- `GET /api/admin/wallets` and `GET /api/admin/validate_wallets` power wallet verification tools.
- `POST` routes such as `/admin/maintenance`, `/admin/recovery/reset`, `/admin/activity/reset`, and `/admin/transfers/*` accept form payloads. When they detect an AJAX request they return JSON (via `_complete_response`) so React components can optimistically update UI state without full page reloads.

All endpoints expect the requester to have an authenticated admin session; the React app will surface authorization failures by showing toast errors.

## Local development tips

1. Run the FastAPI app (for example: `uvicorn main:app --reload --port 8000` from the `ambassadors/fastapi-ambassador-leaderboard` directory).
2. Visit `http://localhost:8000/admin`. The static HTML will load instantly and React will hydrate once the dashboard snapshot resolves.
3. Edit `app.js` or `styles.css` directly and refresh the browser. Because we lean on native ESM imports, changes take effect immediately without rebuilding.
4. To inspect API responses quickly, use your browser's network tab or call the endpoints with `curl -H "Accept: application/json" http://localhost:8000/api/admin/dashboard`.

## Extending the dashboard

- Add new cards or tables by creating React components inside `app.js`. The file is organized into sections (analytics, maintenance, wallets, content moderation, proposals, recoveries, transfers, etc.)—group related UI in those clusters for readability.
- When introducing new backend actions, prefer following the `_complete_response` helper pattern so both form posts and AJAX calls work seamlessly.
- Keep long-running calls on the backend and surface summarized data to the client. This keeps initial render snappy and avoids leaking sensitive operational commands into the browser.

For more context about the FastAPI side of the integration, refer to [`main.py`](../../main.py).
