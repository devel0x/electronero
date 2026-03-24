# Agent Runtime Fabric (MVP)

Production-grade execution layer for BYOK orchestration with a strict tool gateway.

## Tool Contract (ServerBuddy Runtime)

ServerBuddy now supports **both**:

### A) Deployment / app-runtime tools
- `clone_repo`
- `checkout_ref`
- `detect_stack`
- `install_node_deps`
- `install_python_deps`
- `write_env_file`
- `start_process`
- `stop_process`
- `check_port`
- `http_health_check`
- `stream_logs`
- `capture_preview_metadata`
- `export_artifacts`

### B) Safe coding/file toolset
- `run_code`
- `install_package` (recorded/ledgered)
- `read_file`
- `write_file`
- `list_directory`
- `search_in_files`
- `functions_mapping`
- `bracket_tracker`
- `export_artifact`
- `session_reset`

No raw shell endpoint is exposed.

## Architecture

- **Control Plane:** auth/orchestration/policy + job dispatch and ledgering.
- **Operator UI (ServerBuddy):** visual cockpit for approved tools only.
- **Execution Plane:** disposable runtime node with prebaked Node+Python in golden image.
- **Persistence Plane:** external logs and artifacts to survive runtime resets.

## Runtime Filesystem Zones

- `/runtime/workspaces/{session}` writable
- `/runtime/tmp` writable
- `/runtime/output` writable
- `/runtime/cache` writable
- `/runtime/readonly-base` immutable

## Run

```bash
cd agent-runtime-fabric/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
```

Open `frontend/index.html` and set API base to `http://localhost:8080`.
