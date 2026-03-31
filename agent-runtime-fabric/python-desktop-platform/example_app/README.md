# Example App (Vertical Slice)

## Dev

```bash
python -m venv .venv
source .venv/bin/activate
pip install pywebview
python desktop/main.py
```

## Build

```bash
pyinstaller --name sample-workbench --windowed --noconfirm desktop/main.py
```
