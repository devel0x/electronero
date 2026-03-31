# _Gex_UI_UXt

Production-oriented local-first runtime UI for `_Gex` with real repository execution.

## Architecture

- `backend/app.py`: FastAPI API + WebSocket server for repo management, run control, status tracking, and diff retrieval.
- `backend/gex_module`: importable `_Gex` module surface with `GexRunner` and fully programmatic execution methods.
- `frontend`: React + Vite + Tailwind + Monaco editor/diff UI with a 3-pane runtime layout.

## Backend quickstart

```bash
cd _Gex_UI_UXt/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export AIAS_API_KEY=your_key
uvicorn app:app --reload --port 8000
```

## Frontend quickstart

```bash
cd _Gex_UI_UXt/frontend
npm install
npm run dev
```

## Run artifacts

Every execution writes real artifacts under:

- `/workspace/runs/{run_id}/logs.json`
- `/workspace/runs/{run_id}/status.json`
- `/workspace/runs/{run_id}/diffs/*.json`

Repositories are stored under:

- `/workspace/repos/{repo_name}`

## Python module API

```python
from gex_module import GexRunner, GexConfig

runner = GexRunner(GexConfig(api_key="..."))
runner.run_file("/workspace/repos/my_repo/main.py")
runner.run_repo("/workspace/repos/my_repo", mode="sequential")
```
