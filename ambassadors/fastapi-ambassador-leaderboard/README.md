# FastAPI Ambassador Leaderboard

This project is a small FastAPI application that serves an ambassador leaderboard for the Interchained × Elara program. It reads data from a CSV file or a Google Sheet published as CSV, ranks ambassadors by points, and presents both an HTML interface and a JSON API. Pending rewards for each ambassador are calculated by splitting the balance of a configured ITC ambassador pool address in proportion to the ambassadors' points.

## Requirements
- Python 3.11+
- Pinned Python dependencies are listed in `requirements.txt`.

## Running locally
1. **Create a virtual environment and install dependencies**
   ```bash
   cd ambassadors/fastapi-ambassador-leaderboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure the data source**
    - Copy `.env` and edit values as needed. By default the app reads `data/leaderboard.csv`.
    - To use a Google Sheet, publish it to CSV and set `SHEET_CSV_URL` in `.env`.
    - Optionally set `AMBASSADOR_POOL_ADDRESS` so the app can fetch the address balance via `interchained-cli` and show pending rewards.
3. **Run the server**
   ```bash
   uvicorn main:app --reload
   ```
   Visit <http://127.0.0.1:8000> to see the leaderboard.

## Building
There is no special build step for this app. Installing the dependencies and running the FastAPI server is sufficient. For deployment you can use any ASGI server such as `uvicorn` or `gunicorn` with `uvicorn.workers.UvicornWorker`.

## API endpoints
- `GET /` – HTML leaderboard page.
- `GET /api/leaderboard.json` – JSON representation of the leaderboard. Add `?refresh=true` to bypass cache.
- `GET /health` – simple health check.

If `AMBASSADOR_POOL_ADDRESS` is set and `interchained-cli` is available, the app tracks the pool's balance and displays each ambassador's pending reward in both the HTML table and the JSON API response.

## Development notes
- Static files are served from `static/` and templates from `templates/`.
- The app caches data for a configurable TTL to limit repeated downloads of the CSV.

