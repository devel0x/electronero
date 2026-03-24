# ServerBuddy UI (Aceternity-like cockpit)

A dark glassmorphism operator UI for the runtime fabric.

## Files
- `index.html`
- `styles.css`
- `app.js`

## Local preview

```bash
cd agent-runtime-fabric/serverbuddy-ui
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## API wiring

The UI posts to:

- `POST /api/runtime/dispatch`

Expected payload:

```json
{
  "tool": "run_code",
  "session_id": "demo-session",
  "args": {"language": "python", "code": "print('hi')"}
}
```

Wire this endpoint through your Control Plane so auth, policy, and auditing remain centralized.
