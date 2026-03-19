# Node Operator Rewards Portal Frontend

This lightweight frontend provides the neon-glass UI for the Interchained Node Operator Rewards Portal. It is a static site built with vanilla JavaScript and CSS and communicates with the FastAPI backend.

## Usage

1. Serve the files from any static web server (e.g. `python -m http.server` inside the `portal/frontend` directory).
2. The app expects the backend to be available at `http://localhost:8000` by default. Override by setting `window.PORTAL_API_URL` before loading `app.js`.

Example using Python's built-in server:

```bash
cd portal/frontend
python -m http.server 9000
```

Then visit `http://localhost:9000` in your browser.
