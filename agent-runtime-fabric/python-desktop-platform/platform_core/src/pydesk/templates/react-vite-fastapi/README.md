# React + Vite + FastAPI Template

## What you get
- React/Vite frontend in `frontend/`
- FastAPI app in `backend/`
- Desktop shell launcher in `desktop/main.py`
- Manifest-driven runtime/security config in `platform.toml`

## Dev flow

```bash
# Terminal 1
cd frontend
npm install
npm run dev

# Terminal 2
uvicorn backend.main:app --reload

# Terminal 3
python desktop/main.py --dev
```
