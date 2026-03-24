# Agent Runtime Fabric (BYOK Execution Layer)

Production-grade architecture for a **secure, disposable, policy-restricted runtime fabric** where AI agents and users execute code safely.

> This is an execution substrate, not a chatbot backend.

## 1) System Goals

- Safely run untrusted code on low-trust runtime nodes.
- Keep critical state out of runtime nodes.
- Enforce strict policy controls on tools, packages, network, and resources.
- Make runtime nodes disposable: reset frequently and rebuild from golden images.
- Provide an inspectable, operator-friendly cockpit (ServerBuddy).

## 2) Trust & Security Boundaries

### Trust tiers

1. **Control Plane (high trust)**
   - Identity, policy engine, scheduler, metadata store.
   - Never co-located with untrusted runtime execution.
2. **Persistence Plane (high trust)**
   - Artifact store, logs, package ledger, manifests, audit events.
   - Immutable append for critical audit trails.
3. **Execution Plane (low trust / disposable)**
   - Runs user/agent workloads.
   - Treated as potentially compromised at all times.
4. **Operator UI (medium trust)**
   - Calls control-plane APIs only.
   - No direct node SSH or privileged shell.

### Hard boundary rules

- Runtime node cannot reach control-plane internals except scoped APIs.
- Runtime node has no long-lived secrets.
- Runtime-local state is non-authoritative.
- Runtime compromise is contained to session/job scope.

## 3) Layered Architecture

## 3.1 Control Plane

Responsibilities:

- AuthN/AuthZ (user, org, agent identities).
- Policy evaluation per action (`run_code`, `install_package`, `read_file`, etc.).
- Job dispatch and queueing.
- Runtime lifecycle manager (create/reset/destroy).
- Central audit logging + trace correlation.
- Artifact/log indexing and retention controls.

Key services:

- **API Gateway**: signed requests, rate limits, org scoping.
- **Policy Engine**: allow/deny + constraints.
- **Orchestrator**: picks runtime pool/template, schedules jobs.
- **Session Manager**: session TTL, quota, leasing.
- **Runtime Controller**: health checks, snapshot restore, garbage collection.

## 3.2 Operator UI (ServerBuddy)

Capabilities (all tool-mediated):

- Execute code cells/tasks.
- Stream logs and structured events.
- Scoped file browser over allowed directories only.
- Install packages via controlled workflow.
- Export artifacts to persistence plane.

Prohibited:

- Raw unrestricted shell.
- Direct host management actions.
- Any bypass of policy/API gateway.

## 3.3 Execution Plane (Runtime Node)

Runtime node baseline:

- Read-only **golden base** containing OS + Node + Python + baseline libraries.
- Per-session writable overlay mounted to constrained paths.
- Network egress policy with explicit allowlists.
- Cgroup/namespace limits for CPU, memory, pids, and execution TTL.
- Optional syscall filtering (seccomp/AppArmor) for hardening.

### Filesystem zones

- `/runtime/readonly-base` (read-only)
- `/runtime/workspaces/{session}` (writable, session-scoped)
- `/runtime/tmp` (writable, auto-clean)
- `/runtime/output` (writable, exported then purged)
- `/runtime/cache` (writable, bounded, non-authoritative)

## 3.4 Persistence Plane

Stores externally:

- Artifacts (bundles, reports, generated files).
- Logs (stdout/stderr + structured tool logs).
- Execution metadata (job status, durations, resource usage).
- Package manifests + installation ledger.

Design choices:

- Immutable log/event stream for forensics.
- Object storage for artifacts with checksum verification.
- Configurable retention tiers by organization/policy.

## 4) Runtime Lifecycle Model

1. **Provision** from golden image template.
2. **Attach session overlay** and policy profile.
3. **Execute jobs** via tools only.
4. **Pre-reset drain**:
   - flush logs,
   - export artifacts,
   - persist package/session manifest.
5. **Reset/Destroy**:
   - restore pristine snapshot, or terminate node.

Modes:

- **MVP**: pooled nodes with periodic reset (e.g., daily + after high-risk sessions).
- **Target**: ephemeral per-session nodes (strongest isolation, easiest incident containment).

## 5) Tooling Layer Contract

All actions are API tools with policy checks and full auditing.

Core tools:

- `run_code`
- `install_package` (restricted)
- `read_file` / `write_file` (scoped)
- `search_in_files`
- `functions_mapping`
- `bracket_tracker`
- `list_directory`
- `export_artifact`

Recommended additional tools:

- `run_tests`
- `format_code`
- `dependency_audit`
- `resource_usage_snapshot`
- `kill_process`
- `list_processes`
- `network_probe` (policy-gated)

### Tool request model

Each invocation carries:

- `actor_id`, `org_id`, `session_id`, `job_id`
- `tool_name`, `arguments`
- policy context and runtime profile ID

Each result records:

- allow/deny decision + reason
- runtime node ID, timestamps, duration
- CPU/memory peaks, exit code
- artifact references and checksums

## 6) Package Installation Policy

`install_package` workflow:

1. Validate against allowlisted registry/domain.
2. Enforce version policy (pin/upper bound/denylist).
3. Resolve dependency tree (optional SBOM capture).
4. Install only into session-scoped writable environment.
5. Append immutable ledger entry.

Security controls:

- Block post-install scripts unless explicitly allowed.
- Enforce package size/time limits.
- Optionally require pre-approved lockfile for production orgs.

## 7) Resource & Abuse Controls

Per session/job:

- CPU quota + throttling.
- Memory hard limit (OOM kill + structured error).
- Wall-time TTL with graceful then forced termination.
- Process count and file descriptor caps.
- Output size limits + truncation policy.

System-wide:

- Fair-share scheduler and org quotas.
- Burst handling with queue backpressure.
- Automatic quarantine of anomalous sessions.

## 8) Network Isolation Model

Default: deny egress except allowlisted destinations required for tasks.

Profiles:

- **offline**: no network
- **restricted**: registry + approved APIs only
- **extended**: broader outbound for specific jobs with approval

Always block:

- metadata endpoints
- control plane private subnets
- east-west runtime lateral movement

## 9) MVP Blueprint (Simple, Scalable)

Start with these pragmatic choices:

- Shared worker pool (small autoscaled group).
- Golden image with pre-baked Node + Python + common tooling.
- Session overlays for writable state.
- Daily reset + on-demand reset button.
- Mandatory tool mediation; no raw shell.
- External object store + log pipeline as system of record.

Why this works:

- Fast to ship.
- Strong baseline containment.
- Clear path to per-session ephemeral runtimes later.

## 10) Evolution Path

1. **MVP pooled runtimes** (reset-based hygiene).
2. **Ephemeral session runtimes** with one-session-one-node model.
3. **Golden image promotion** pipeline (dev → staging → prod).
4. **Runtime templates** (data science, web, automation).
5. **Multi-agent collaboration** with shared artifact bus and scoped permissions.

## 11) Failure Strategy

Assume compromise and design graceful degradation:

- Kill/replace node, never repair in place.
- Rehydrate from golden image automatically.
- Preserve evidence via externalized logs/artifacts.
- Rotate credentials/tokens that were session-scoped.

## 12) Definition of Done

A runtime fabric is production-ready when:

- No critical state depends on runtime-local disk.
- All execution actions are tool-mediated and auditable.
- Runtime reset/destroy is routine and automated.
- Policy violations are blocked with clear operator feedback.
- Compromised node impact is bounded to disposable compute.

---

## Reference Principle

**Serverless for agents, but inspectable and controllable.**
