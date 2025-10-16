# Ambassador OTC Desk Preview Guide

This guide captures the environment variables and runtime steps used to preview the ambassador OTC desk locally.

## Prerequisites

* Python 3.12 with `venv`
* Redis server running on `localhost:6379`

Install Python dependencies into a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn aiofiles jinja2 python-dotenv redis pandas httpx requests python-multipart
```

Start Redis (if it is not already running):

```bash
redis-server --daemonize yes
```

## Launching the FastAPI app

Set the CSV paths so the leaderboard data loads correctly before starting Uvicorn:

```bash
export CSV_PATH=ambassadors/fastapi-ambassador-leaderboard/data/leaderboard.csv
export REGISTRATIONS_CSV=ambassadors/fastapi-ambassador-leaderboard/data/registrations.csv
uvicorn ambassadors.fastapi-ambassador-leaderboard.main:app --host 0.0.0.0 --port 8000 --reload
```

## Creating a test ambassador

With Redis running, seed a verified ambassador account so you can sign in and access `/otc`:

```python
from redis import Redis
import hashlib
client = Redis.from_url('redis://localhost:6379/0', decode_responses=True)
email = 'previewer@example.com'
password = 'password123'
client.hset(f'user:{email}', mapping={
    'password': hashlib.sha256(password.encode()).hexdigest(),
    'verified': 1,
    'telegram': '@previewer',
    'wallet': 'itc1previewwallet'
})
client.hset('score_pad', email, 1000)
```

After logging in at `http://localhost:8000/login` with the seeded credentials, open the OTC desk at `http://localhost:8000/otc` to view the trading interface.
