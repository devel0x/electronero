# Threads Contest Engine

A minimal full-stack MVP with FastAPI + Redis backend and Next.js frontend.

## Quickstart

```bash
cd backend
docker compose up -d
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd ../frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:8000
