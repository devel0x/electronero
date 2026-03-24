# Agent Runtime Fabric (MVP)

Production-grade **execution layer** for a BYOK AI orchestration platform.

This project models a secure, disposable runtime fabric where code execution is isolated from the control plane and all durable state is externalized.

## Goals

- Treat runtime nodes as **low-trust disposable compute**.
- Enforce execution only via a **tooling gateway**, not unrestricted shell.
- Keep critical data in an external persistence plane.
- Support periodic snapshot resets and evolution toward ephemeral session runtimes.

## Layered Architecture

### 1) Control Plane (`backend/` APIs)

Responsibilities:

- Auth/session validation (stubbed for MVP)
- Orchestration and policy checks
- Runtime lifecycle control (create session, reset, destroy)
- Job dispatch and metadata recording
- Tool permission checks and installation restrictions

### 2) Operator UI / ServerBuddy (`frontend/`)

- Job composer for `run_code`
- Package installs through restricted `install_package`
- Filesystem explorer for allowed zones only
- Session policy and runtime status visibility
- Artifact export action

### 3) Execution Plane (Runtime Node abstraction)

Filesystem zones:

- `/runtime/workspaces/{session}` writable
- `/runtime/tmp` writable
- `/runtime/output` writable
- `/runtime/cache` writable with quotas
- `/runtime/readonly-base` immutable baseline

Security assumptions:

- Runtime is disposable and can be compromised
- No sensitive credentials on runtime node
- Strict TTL, CPU, memory, and network policy

### 4) Persistence Plane (`persistence/` as MVP placeholder)

Externalized durability for:

- tool ledger
- execution logs
- output artifacts
- package manifest and install history

## Tooling Surface

All execution is mediated through the following APIs/tools:

- `run_code`
- `install_package`
- `read_file`
- `write_file`
- `search_in_files`
- `functions_mapping`
- `bracket_tracker`
- `list_directory`
- `export_artifact`
- `session_reset`

## Security Model Highlights

- No raw shell endpoint in UI.
- Command execution goes through `run_code` policy checks.
- Package installs:
  - allowlisted registries (`pypi.org`, `registry.npmjs.org`)
  - optional pinning policy
  - immutable install ledger
- Resource guards:
  - per-job timeout
  - max output bytes
  - deny blocked path traversal

## Lifecycle

1. Session is created from golden image metadata.
2. Jobs execute in scoped workspace.
3. Logs/artifacts are externalized.
4. Runtime is reset or destroyed.
5. Fresh baseline restored from golden image.

## Run MVP

```bash
cd agent-runtime-fabric/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
```

Then open `frontend/index.html` in a browser and point API base to `http://localhost:8080`.

## Evolution Path

- Swap in per-session microVM containers
- Add image promotion pipeline for `readonly-base`
- Add multi-agent cooperative sessions
- Add runtime templates for data science / web / automation
