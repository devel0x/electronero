# Threads Contest Engine Backend

## Setup

```bash
docker compose up -d
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Notes
- Redis uses DB 7 by default (`redis://localhost:6379/7`).
- CORS is enabled for `http://localhost:3000`.
