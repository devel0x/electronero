# Server-less Sandboxed Agentic Runtime (Python + Node.js)

This package is a production-leaning MVP runtime layer for policy-mediated execution.

## Hardened runtime capabilities

- No raw shell endpoint; only explicit tool dispatch.
- Per-session scoped workspace and path traversal protection.
- Request validation for tool name, session id, payload shape.
- CPU + memory + execution-time limits on subprocess execution.
- Tool allowlist and package registry allowlist enforcement.
- Optional package version pin enforcement via policy.
- Size limits for code payloads and file writes.
- Append-only JSONL audit ledger with argument/result hashes.

## Implemented tools

- `run_code`
- `install_package`
- `read_file`
- `write_file`
- `search_in_files`
- `functions_mapping`
- `bracket_tracker`
- `list_directory`
- `export_artifact`
- `reset_session`

## Runtime entrypoint

- `src/runtime_fabric.py`

## Test and smoke commands

```bash
cd agent-runtime-fabric/serverless-runtime
make test
make smoke
```

## Integration note

Use this runtime behind a Control Plane endpoint (`/api/runtime/dispatch`) that injects org/actor context and enforces authN/authZ before dispatching tools.
