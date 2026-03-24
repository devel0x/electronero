# ServerBuddy Runtime (full tool surface)

This runtime now exposes the **full toolset** for both repo/devops flows and coding/runtime flows.

## Tool groups

### Repo / process / preview tools
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

### Coding/runtime tools
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

## Security posture

- Tool allowlist enforced by policy.
- Workspace confinement per session.
- Tool calls audited in `audit-ledger.jsonl`.
- No unrestricted shell endpoint.

## Test and smoke

```bash
cd agent-runtime-fabric/serverless-runtime
make lint
make test
make smoke
```
