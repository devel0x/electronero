# _Gex_UI_UX

A modern, "native-feel" Electron UI to:

- Open a local repository/folder.
- Inspect source files with Monaco.
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
2. Select a file in the explorer to load it in Monaco.
3. Run **Scan Current File** to execute `_Gex <file>`.
4. Use **Queue Current** + **Run Queue (1-by-1)** to process files sequentially.
5. Review changes in the diff pane.

## Notes

- The `_Gex` command defaults to `_Gex` and can be changed from the top-right command input.
- The app compares file contents before and after each run to render diffs.
