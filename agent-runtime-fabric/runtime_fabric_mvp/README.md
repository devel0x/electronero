# Runtime Fabric MVP (Python + Node.js)

This is a minimal **serverless-style sandboxed agent runtime** prototype for Python and Node.js workloads.

## What this build provides

- Control-plane API using FastAPI.
- Tool-mediated execution only:
  - `run_code`
  - `install_package` (registry-restricted)
  - `export_artifact`
- Session workspaces with scoped paths under `.runtime/`.
- Policy loading from `../mvp-policy.yaml`.
- Easy migration path to ephemeral per-session workers.

## Directory layout

- `control_plane.py` — API gateway and orchestration entrypoints.
- `runtime_worker.py` — low-trust execution worker.
- `policy.py` — policy loading and enforcement guards.
- `schemas.py` — request/response schema contract.
- `requirements.txt` — Python dependencies.

## Run locally

```bash
cd agent-runtime-fabric/runtime_fabric_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn control_plane:app --reload --port 8080
```

## Example flow

1) Create session:

```bash
curl -s -X POST http://127.0.0.1:8080/sessions
```

2) Execute Python code:

```bash
curl -s -X POST http://127.0.0.1:8080/tools/run_code \
  -H 'content-type: application/json' \
  -d '{
    "session_id":"sess-REPLACE",
    "language":"python",
    "code":"print(2+2)",
    "timeout_seconds":10
  }'
```

3) Execute Node.js code:

```bash
curl -s -X POST http://127.0.0.1:8080/tools/run_code \
  -H 'content-type: application/json' \
  -d '{
    "session_id":"sess-REPLACE",
    "language":"nodejs",
    "code":"console.log(2+3)",
    "timeout_seconds":10
  }'
```

4) Install package via allowlisted registry:

```bash
curl -s -X POST http://127.0.0.1:8080/tools/install_package \
  -H 'content-type: application/json' \
  -d '{
    "session_id":"sess-REPLACE",
    "language":"python",
    "registry":"pypi.org",
    "package":"requests",
    "version":"2.32.3"
  }'
```

## Notes on production hardening

This MVP intentionally keeps implementation simple. In production, layer in:

- gVisor/Firecracker/Kata for stronger sandboxing.
- cgroup enforcement + seccomp profiles.
- signed job tokens and per-job credentials.
- append-only audit store and remote log sink.
- worker autoscaling and queue backpressure.
