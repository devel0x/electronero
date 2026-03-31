# _Gex_UI_UX

A modern Microsoft + Bloomberg-terminal style Electron UI to:

- Open a local repository/folder.
- Inspect source files with Monaco.
- Install `_Gex` from GitHub as a local module (`modules/_Gex`).
- Run `_Gex` against a single file.
- Queue files and run `_Gex` one file at a time.
- View before/after diffs for each run.

## Quick start

```bash
cd _Gex_UI_UX
npm install
npm start
```

## Workflow

1. Click **Open Folder** and pick the repository you want to inspect.
2. Click **Install/Update _Gex Module** once (or whenever you want the latest _Gex).
3. Select a file in the explorer to load it in Monaco.
4. Choose an **Output Mode**:
   - `Create *_gex file next to target` → writes `<filename>_gex.<ext>`
   - `Clone repo to *_Gex then scan` → clones your repo into `<repo>_Gex/` and scans there
5. Run **Scan Current File**.
6. Use **Queue Current** + **Run Queue (1-by-1)** to process files sequentially.
7. Review changes in the diff pane.

## Notes

- `_Gex` is auto-cloned from `https://github.com/aiassistsecure/_Gex` into `modules/_Gex`.
- The app invokes `_Gex.py` with: `python3 _Gex.py --scan <root> --file <relative-file>`.
- The app compares file contents before and after each run to render diffs.
