# Coding Automation SLM (Standalone)

This folder contains a **small, standalone language model** focused on coding automation and intent routing.

It is designed to run with the Python standard library only.

## What it does

- Trains a tiny Naive Bayes intent model at startup.
- Detects coding intents such as:
  - `code_generation`
  - `debugging`
  - `refactor`
  - `internet_lookup`
  - `run_command`
- Routes intent to pluggable tools:
  - `shell` plugin for local coding commands (`git`, `python`, `cmake`, `make`, `rg`)
  - `web_search` plugin for public web lookup
  - `http_tool` plugin to call arbitrary HTTP/JSON endpoints

This gives you a compact foundation for a coding-focused assistant that can be extended with any internet service.

## Quick start

From repo root:

```bash
python3 tools/coder_intent_slm/main.py "search latest docs for python subprocess" --query "python subprocess docs"
```

Run command automation:

```bash
python3 tools/coder_intent_slm/main.py "run git status" --command "git status"
```

Call any internet API endpoint:

```bash
python3 tools/coder_intent_slm/main.py \
  "find current UTC time from an api" \
  --plugin http_tool \
  --query "https://worldtimeapi.org/api/timezone/Etc/UTC"
```

## Architecture

- `model.py`: Tiny intent classifier.
- `agent.py`: Intent inference and tool routing.
- `plugins.py`: Plugin protocol and built-in plugin implementations.
- `main.py`: CLI interface.

## Notes

- This is intentionally small and deterministic to keep it standalone.
- You can extend it by adding your own plugin class in `plugins.py` and mapping it in `agent.py`.
