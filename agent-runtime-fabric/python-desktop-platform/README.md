# PyDesk Platform (V1 Proposal + Vertical Slice)

A production-oriented blueprint and starter scaffold for **"Electron for Python, but better"**.

---


## V2-ready upgrades in this repo

- Permission-aware bridge path validation via app manifest roots.
- Runtime plugin loading with explicit `PLUGIN` registration contract.
- CLI `validate` and `add-plugin` commands for safer lifecycle operations.
- Manifest runtime toggles (`[runtime].plugins_enabled`) for enterprise hardening.

---

## Production-ready hardening included

- Strict manifest validation with explicit `ConfigError` and minimum window constraints.
- Safer filesystem permission checks using canonical path containment (`relative_to` semantics).
- Plugin allowlisting and strict-mode controls (`plugin_allowlist`, `strict_plugins`).
- CLI machine-readable diagnostics via `pydesk validate --json` and `pydesk doctor --json`.

---

## 1) Product Definition

### What it is
PyDesk is a Python-native desktop application platform combining:
- a lightweight desktop shell,
- a modern frontend (web stack by default),
- a typed Python runtime bridge,
- opinionated templates,
- one-command packaging + release workflows.

### Who it is for
- SaaS teams shipping internal tools.
- AI product teams building local/edge assistants.
- Dev-tools teams building IDE-like clients.
- Enterprise teams needing secure, auditable desktop apps.

### Why it should exist
Developers want web-like speed for desktop, but Electron’s Node/runtime overhead and bundle bloat are painful. Python teams want to reuse backend/AI/data libraries directly in desktop apps.

### Why Python is the right foundation
- Dominant language for AI, automation, data tooling.
- Strong mature packaging ecosystem.
- Rich OS and subprocess integration.
- Excellent developer productivity and readability.

### Core value proposition
**Build desktop apps with modern web ergonomics and Python-native power, then package and ship with production defaults.**

### How it differs
- **vs Electron:** Python runtime first, smaller mental model for Python teams, fewer JS-only constraints.
- **vs PyInstaller-only:** full platform conventions (CLI/templates/bridge/dev mode), not just freezing scripts.
- **vs Tauri:** Python-native runtime model instead of Rust-centric host.
- **vs Qt-only:** modern web UI workflow + component ecosystem by default.
- **vs browser wrappers:** explicit desktop bridge, permissioned APIs, packaging and updates from day one.

---

## 2) Architecture Options

| Option | Runtime Model | UI Model | Bridge | Packaging | Strengths | Weaknesses | Best For |
|---|---|---|---|---|---|---|---|
| A. Embedded WebView + Python Host | Python process owns app lifecycle | React/Vue/Svelte in embedded webview | Local JS bridge (RPC-like) | PyInstaller/Nuitka + native installer | Fast DX, easy template reuse, low ceremony | Webview engine variance by OS | Internal tools, AI clients |
| B. Python-native UI (Qt/Toga) | Python process | Native widgets | In-process direct calls | PyInstaller + Qt deploy tooling | Native-feeling controls, no web stack | Slower UI velocity for web teams | Utility apps, form-heavy clients |
| C. Hybrid Local Server + Desktop Shell | Python local server + shell process | Browser-style SPA served locally | HTTP/WS + signed command channel | Bundle server + static assets + shell | Clear boundaries, scalable plugin model | More moving parts | IDE/workbench, plugin-heavy apps |
| D. Agentic Runtime + Tool Bus | Python runtime sandbox + tool adapters | Webview/Native mixed | Tool protocol + policy engine | Containerized + desktop launcher | Great for secure AI workflows | Highest complexity | Enterprise AI workbenches |

### Recommended V1 default
**Option A: Embedded WebView + Python host** with a small optional local service loop.

Why:
- Minimal dependency surface.
- Fastest scaffold-to-running app time.
- Easy migration path toward Option C later.

---

## 3) V1 Platform Design

### V1 components
- `pydesk` CLI scaffolder.
- Template registry + metadata.
- Desktop runtime host (window lifecycle + bridge).
- Desktop API bridge (filesystem/system/dialog subset).
- Build commands for frozen binaries.
- Convention-based app manifest (`platform.toml`).

### Developer experience flow
```bash
pydesk new my-app --template ai-chat
cd my-app
pydesk dev
pydesk build --target macos
pydesk package --installer
pydesk release --channel stable
```

### Folder conventions
```text
my-app/
  platform.toml
  frontend/
  backend/
  desktop/
  plugins/
  tests/
```

---

## 4) Templates Strategy

1. **blank-app** — minimal shell + bridge + hello UI.
2. **dashboard-app** — cards/charts, auth shell, table/grid basics.
3. **ai-chat-client** — streaming chat UI, model adapter interface, local history.
4. **local-first-crud** — SQLite repo, sync hooks, optimistic UI.
5. **settings-utility** — tray + settings pages + background checks.
6. **ide-workbench** — split panes, file tree, terminal process adapter.
7. **admin-ops-tool** — role-aware views, audit trail panel, task runners.

Template composition:
- base `blank-app` + features (`auth`, `sqlite`, `tray`, `updater`, `ai`).
- deterministic merge via template manifest dependencies.

---

## 5) Agentic Layer

Agent-ready design:
- `platform.toml` as source-of-truth manifest.
- `template.yaml` machine-readable metadata (`inputs`, `features`, `patches`).
- Generated files under `generated/` with lock comments.
- Agent-safe edit regions:
  - `# pydesk:begin user` / `# pydesk:end user`
  - `// pydesk:slot main-nav`
- `pydesk doctor --json` for machine diagnostics.
- `pydesk upgrade` applies versioned migrations.

---

## 6) Desktop Capabilities (API Surface)

Example bridge namespaces:
- `fs.read_text(path)`, `fs.write_text(path, data)`
- `storage.get(key)`, `storage.set(key, value)`
- `notifications.send(title, body)`
- `window.minimize()`, `window.toggle_fullscreen()`
- `clipboard.read()`, `clipboard.write(text)`
- `dialogs.open_file()`
- `process.run(cmd, args, policy='restricted')`
- `service.start_http(port)`
- `secrets.get(name)`
- `updater.check()`

Each endpoint has:
- permission key,
- runtime-side validation,
- audited invocation log.

---

## 7) Security Model

Trust boundaries:
- Frontend is untrusted UI layer.
- Python host is trusted policy enforcement point.
- Optional plugin code is semi-trusted, capability-scoped.

Controls:
- Permission-gated bridge endpoints.
- App manifest allowlist for filesystem roots and subprocesses.
- No arbitrary eval bridge endpoints.
- Signed update manifests + signature verification.
- Enterprise mode: disable dynamic plugins, enforce signed plugins only.

---

## 8) Build, Packaging, Distribution

Dev:
- `pydesk dev`: starts runtime + local static frontend server + reload loop.

Prod:
- freeze Python runtime (default PyInstaller, optional Nuitka).
- bundle frontend static assets.
- produce OS-native installer artifacts.

Defaults:
- macOS: `.app` + notarization hooks.
- Windows: `.exe` + MSIX/NSIS option.
- Linux: AppImage + `.deb` metadata support.

Reproducibility:
- lockfile required,
- deterministic asset hashing,
- build metadata captured in `dist/build-manifest.json`.

---

## 9) Tech Stack Recommendation (V1)

- **Shell/WebView:** `pywebview`
  - Why: mature, cross-platform, simple Python integration.
  - Alternative: CEF wrappers (heavier), QtWebEngine (larger footprint).
- **CLI:** `Typer`
  - Why: typed commands, fast authoring, clean help UX.
- **Config:** `TOML` (`platform.toml`)
  - Why: Python-native parsing in stdlib (`tomllib`) on 3.11+.
- **Frontend default:** `Vite + React + TypeScript`
  - Why: dominant ecosystem, template richness, quick HMR.
- **Packaging default:** `PyInstaller`
  - Why: lowest friction cross-platform starter.
  - Optional: `Nuitka` for performance/obfuscation tradeoffs.
- **Testing:** `pytest` + smoke E2E command checks.

---

## 10) Developer Experience

Command set:
- `pydesk new`
- `pydesk dev`
- `pydesk build`
- `pydesk package`
- `pydesk release`
- `pydesk doctor`
- `pydesk add template`
- `pydesk add feature`
- `pydesk add plugin`

DX principles:
- one command to start,
- meaningful errors with remediation hints,
- strict conventions with escape hatches.

---

## 11) Branding / Positioning

### Positioning
Python-first desktop platform for teams shipping modern apps fast.

### Landing headline
**Ship Python desktop apps at web speed.**

### Tagline
**Modern desktop, native Python.**

### 3 differentiators
1. Python-native runtime bridge for AI/data workflows.
2. Template + agent-aware architecture.
3. Packaging/release pipeline as a first-class concern.

### Why now
AI-native products need local compute, secure data handling, and desktop UX.

### Candidate names (10)
1. PyDesk
2. DeskForge
3. RuntimeDock
4. AltairDesk
5. FluxDesktop
6. CraftPane
7. WorkbenchPy
8. LocalOrbit
9. ShellWeave
10. NativeCanvas

---

## 12) Competitive Analysis

- **Electron:** best ecosystem; weaker for Python-native execution and memory footprint.
- **Tauri:** excellent lightweight shell; Rust-first runtime makes Python workflows indirect.
- **PyInstaller-only:** good binary creation; lacks framework conventions and bridge architecture.
- **PySide/PyQt:** powerful native UI; slower frontend iteration for web teams.
- **Neutralino:** lightweight; less opinionated full-stack developer platform story.
- **Browser wrappers:** fast demos, weaker desktop integration/security posture.

Where PyDesk can win:
- AI/data + enterprise desktop combo with Python-first productivity.

---

## 13) V1 Scope vs Future Scope

### V1 (must ship)
- CLI scaffolding.
- Embedded webview shell.
- Secure bridge with basic APIs.
- 3 high-value templates.
- Build/package commands.

### V2+
- signed plugin marketplace,
- differential auto-update channels,
- enterprise policy packs,
- remote fleet/telemetry controls.

Roadmap note: do **not** attempt “v2.2.2 all at once”; ship V1 vertical slice first.

---

## 14) Suggested File/Code Scaffold

See `platform_core/` and `example_app/` in this folder for a working vertical slice.

---

## 15) Implementation Plan

### Phase 0 — Prototype
- Goal: prove shell + bridge + frontend call.
- Deliverable: local demo app.
- Risk: unstable webview behavior across OS.
- Validation: one-click run on all 3 OSes.

### Phase 1 — Minimal Platform
- Goal: CLI + templates + packaging.
- Deliverable: `pydesk new/dev/build`.
- Risk: packaging edge cases.
- Validation: generated app runs frozen.

### Phase 2 — Usable Framework
- Goal: permissions, plugins, better DX.
- Deliverable: plugin API + doctor/upgrade.
- Risk: plugin trust model complexity.
- Validation: internal reference apps ship.

### Phase 3 — RC Polish
- Goal: updater/signing/docs hardening.
- Deliverable: release candidate.
- Risk: code signing CI complexity.
- Validation: enterprise pilot deployment.

---

## 16) Opinionated Recommendation

- **Best architecture:** Embedded webview + Python host (Option A) with migration path to hybrid server shell.
- **Best V1 stack:** pywebview + Typer + TOML + PyInstaller + React/Vite templates.
- **Most important technical risk:** secure, stable bridge + cross-platform packaging drift.
- **Most important product risk:** over-building before validating template demand.
- **Build first this week:** CLI `new/dev`, minimal bridge (`system_info`), one template, frozen build smoke test.

---

## Executive Summary
PyDesk should launch as a Python-first desktop platform with template-driven scaffolding, a secure bridge, and frictionless shipping. Win initial adoption with internal tools + AI clients where Python-native capabilities matter more than maximal UI novelty.

## Build-this-first MVP Spec
- `pydesk new` from `blank-app`.
- `pydesk dev` launches app window and frontend.
- frontend calls `system_info` via bridge.
- `pydesk build` creates distributable binary.

## Open Technical Questions
1. How strict should default bridge permissions be for developer velocity?
2. Should frontend serve via dev server in V1 or bundled static-only?
3. PyInstaller vs Nuitka default for enterprise customers?
4. Best cross-platform installer abstraction strategy?
5. Plugin signature format (Sigstore/COSIGN/GPG)?

---

## Sample README for Generated App

```md
# My PyDesk App

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pydesk dev
```

## Build

```bash
pydesk build
pydesk package
```

## Native Bridge Example

Frontend:
```ts
const info = await window.pywebview.api.get_system_info();
```
```

## Sample `platform.toml`

```toml
[app]
name = "my-app"
id = "com.example.myapp"
version = "0.1.0"

[desktop]
width = 1200
height = 780

[permissions]
filesystem = ["./data"]
subprocess = false
clipboard = true
notifications = true

[build]
tool = "pyinstaller"
entrypoint = "desktop/main.py"
```
