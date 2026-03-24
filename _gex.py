#!/usr/bin/env python3
"""
Gex — AI Code Surgeon
Scans source code, clones the repo to a parallel directory, asks the LLM
for surgical fixes using <<<WRITE>>> / <<<PATCH>>> patterns, applies them
to the clone, and posts a detailed summary to an AiAS workspace.

Supports single-file (--file) or full-repo (--scan) modes.

Surgical edit patterns (Keystone-lite):
  <<<WRITE:path/to/file>>>   — full file overwrite in clone
  <<<PATCH:path/to/file>>>   — line-based operations (replace/insert/delete)
  <<<END>>>                  — terminates a WRITE or PATCH block

Usage:
  python gex.py --scan ./myproject
  python gex.py --scan ./myproject --file src/auth.py
  python gex.py --scan ./myproject --file src/auth.py --focus "fix the login bug"
  python gex.py --scan ./myproject --dry-run
  python gex.py --list-workspaces
"""

import os
import sys
import json
import hashlib
import argparse
import shutil
import re
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

API_BASE = os.getenv("AIAS_API_URL", "https://api.aiassist.net")
API_KEY = os.getenv("AIAS_API_KEY", "aai_08Yje_4t11_r4zxMMxOWymYht5pbx2ASvRwJB0wKasc")
MODEL = os.getenv("AIAS_MODEL", "moonshotai/kimi-k2-instruct")
PROVIDER = os.getenv("AIAS_PROVIDER", "groq")

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", ".next", ".cache", "appendonlydir",
    "redis-data", ".local", ".replit", ".upm", "_gex",
}
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "dump.rdb", ".DS_Store",
}
CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go",
    ".java", ".css", ".html", ".sql", ".sh", ".toml", ".yaml", ".yml",
}
MAX_FILE_SIZE = 200_000
MAX_CONTEXT_CHARS = 100_000

auth_headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
if PROVIDER:
    auth_headers["X-AiAssist-Provider"] = PROVIDER


def scan_tree(root: str, focus_file: str = None) -> list[dict]:
    root_path = Path(root).resolve()
    files = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix not in CODE_EXTENSIONS:
            continue
        if focus_file and focus_file not in str(path):
            continue
        rel = str(path.relative_to(root_path))
        try:
            size = path.stat().st_size
            content = path.read_text(errors="replace")
            if size > MAX_FILE_SIZE:
                lines = content.split("\n")
                max_lines = MAX_FILE_SIZE // 80
                content = "\n".join(lines[:max_lines]) + f"\n\n# ... truncated ({len(lines) - max_lines} more lines)"
            files.append({"path": rel, "size": size, "content": content, "lines": content.count("\n") + 1})
        except Exception as e:
            files.append({"path": rel, "error": str(e)})
    return files


def build_context(files: list[dict], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    parts = []
    total = 0
    for f in files:
        content = f.get("content", f.get("error", ""))
        numbered = "\n".join(f"{i+1:>4}| {line}" for i, line in enumerate(content.split("\n")))
        header = f"### {f['path']} ({f.get('lines', '?')} lines)\n"
        block = f"```\n{numbered}\n```\n"
        chunk = header + block
        if total + len(chunk) > max_chars:
            parts.append(f"### {f['path']}\n[truncated: context limit reached]\n")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)


def build_tree_summary(files: list[dict]) -> str:
    return "\n".join(f"  {f['path']}  ({f.get('lines', '?')} lines, {f.get('size', 0)} bytes)" for f in files)


def send_to_llm(client: httpx.Client, system_prompt: str, user_msg: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
        "max_tokens": 16384,
    }
    resp = client.post(f"{API_BASE}/v1/chat/completions", json=payload, headers=auth_headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"] or ""
    if not content.strip():
        print(f"[!] LLM returned empty content.")
        print(json.dumps(data, indent=2)[:2000])
    return content


def create_workspace(client: httpx.Client, name: str) -> Optional[dict]:
    resp = client.post(f"{API_BASE}/api/workspaces", json={
        "initial_message": f"Gex surgery workspace: {name}",
        "client_id": f"gex_{hashlib.md5(name.encode()).hexdigest()[:12]}",
    }, headers=auth_headers, timeout=30)
    if resp.status_code == 401:
        print("[!] API key auth failed. Check AIAS_API_KEY.")
        return None
    resp.raise_for_status()
    return resp.json()


def store_in_workspace(client: httpx.Client, workspace_id: str, content: str):
    resp = client.post(
        f"{API_BASE}/api/workspaces/{workspace_id}/messages",
        json={"content": content},
        headers=auth_headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[!] Failed to store in workspace: {resp.status_code}")


def clone_repo(source: str) -> str:
    source_path = Path(source).resolve()
    clone_path = source_path.parent / f"{source_path.name}_gex"

    if clone_path.exists():
        print(f"       Cleaning existing clone: {clone_path.name}/")
        shutil.rmtree(clone_path)

    print(f"       Cloning to: {clone_path.name}/")
    shutil.copytree(
        source_path, clone_path,
        ignore=shutil.ignore_patterns(*SKIP_DIRS, *SKIP_FILES),
        dirs_exist_ok=False,
    )
    return str(clone_path)


def parse_surgical_blocks(llm_output: str) -> list[dict]:
    blocks = []
    pattern = re.compile(r'<<<(WRITE|PATCH):(.+?)>>>\s*\n(.*?)<<<END>>>', re.DOTALL)

    for match in pattern.finditer(llm_output):
        action = match.group(1)
        filepath = match.group(2).strip()
        body = match.group(3)

        if action == "WRITE":
            blocks.append({"action": "write", "path": filepath, "content": body.rstrip("\n")})
        elif action == "PATCH":
            try:
                ops_data = json.loads(body.strip())
                operations = ops_data if isinstance(ops_data, list) else ops_data.get("operations", [ops_data])
                blocks.append({"action": "patch", "path": filepath, "operations": operations})
            except json.JSONDecodeError as e:
                print(f"[!] Failed to parse PATCH JSON for {filepath}: {e}")
                blocks.append({"action": "patch_error", "path": filepath, "raw": body, "error": str(e)})

    return blocks


def apply_patch_operations(content: str, operations: list[dict]) -> tuple[str, int, int]:
    lines = content.split("\n")
    added = 0
    removed = 0

    sorted_ops = sorted(operations, key=lambda op: op.get("start_line", 0), reverse=True)

    for op in sorted_ops:
        action = op.get("action", "replace")
        start = op.get("start_line", 1)
        start_idx = start - 1

        if action == "insert":
            new_lines = op.get("content", "").split("\n")
            lines = lines[:start_idx] + new_lines + lines[start_idx:]
            added += len(new_lines)

        elif action == "replace":
            end_idx = op.get("end_line", start)
            new_lines = op.get("content", "").split("\n")
            old_count = end_idx - start_idx
            lines = lines[:start_idx] + new_lines + lines[end_idx:]
            added += len(new_lines)
            removed += old_count

        elif action == "delete":
            end_idx = op.get("end_line", start)
            old_count = end_idx - start_idx
            lines = lines[:start_idx] + lines[end_idx:]
            removed += old_count

    return "\n".join(lines), added, removed


def validate_clone_path(clone_path: str, filepath: str) -> Optional[Path]:
    clone_root = Path(clone_path).resolve()
    candidate = (clone_root / filepath).resolve()
    if not str(candidate).startswith(str(clone_root) + os.sep) and candidate != clone_root:
        return None
    return candidate


def apply_blocks_to_clone(clone_path: str, blocks: list[dict]) -> list[dict]:
    results = []
    for block in blocks:
        filepath = block["path"]
        full_path = validate_clone_path(clone_path, filepath)

        if full_path is None:
            results.append({"path": filepath, "action": block["action"].upper(), "status": "blocked", "detail": "path traversal detected — skipped"})
            print(f"       BLOCK  {filepath}  [PATH TRAVERSAL — REJECTED]")
            continue

        if block["action"] == "write":
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(block["content"])
            results.append({"path": filepath, "action": "WRITE", "status": "applied", "detail": f"wrote {len(block['content'])} chars"})
            print(f"       WRITE  {filepath}")

        elif block["action"] == "patch":
            if not full_path.exists():
                results.append({"path": filepath, "action": "PATCH", "status": "skipped", "detail": "file not found in clone"})
                print(f"       PATCH  {filepath}  [SKIP — not found]")
                continue
            original = full_path.read_text(errors="replace")
            try:
                new_content, added, removed = apply_patch_operations(original, block["operations"])
                full_path.write_text(new_content)
                results.append({
                    "path": filepath, "action": "PATCH", "status": "applied",
                    "detail": f"+{added} -{removed} lines, {len(block['operations'])} ops",
                })
                print(f"       PATCH  {filepath}  (+{added} -{removed})")
            except Exception as e:
                results.append({"path": filepath, "action": "PATCH", "status": "error", "detail": str(e)})
                print(f"       PATCH  {filepath}  [ERROR: {e}]")

        elif block["action"] == "patch_error":
            results.append({"path": filepath, "action": "PATCH", "status": "parse_error", "detail": block["error"]})
            print(f"       PATCH  {filepath}  [PARSE ERROR]")

    return results


GEX_SYSTEM_PROMPT = """You are Gex, an expert code surgeon. You analyze source code and produce precise, surgical fixes.

You MUST use these exact block formats for ALL code changes:

## <<<WRITE:path/to/file>>>
Use for NEW files or FULL rewrites (>50% of file changes). Write the complete file content between the tags.
```
<<<WRITE:src/utils/helper.py>>>
def helper():
    return "fixed"
<<<END>>>
```

## <<<PATCH:path/to/file>>>
Use for TARGETED edits (1-30 lines changing). Provide a JSON array of operations:
```
<<<PATCH:src/auth.py>>>
[
  {"action": "replace", "start_line": 15, "end_line": 20, "content": "    return validate(token)"},
  {"action": "insert", "start_line": 5, "content": "import hashlib"},
  {"action": "delete", "start_line": 42, "end_line": 45}
]
<<<END>>>
```

### Operation types:
- **replace**: Replace lines start_line through end_line with new content
- **insert**: Insert content BEFORE start_line (existing code shifts down)
- **delete**: Remove lines start_line through end_line

### Rules:
1. Reference EXACT line numbers from the numbered source code provided
2. For replace: ALWAYS include the full line range (start to end of the block being replaced)
3. Keep patches minimal — change only what needs fixing
4. Never use placeholders like "// rest of code here"
5. Provide a clear explanation BEFORE each block explaining what you're fixing and why
6. After all blocks, provide a ## Summary section listing all changes made

If no fixes are needed, say so clearly and explain why the code is already correct."""


def build_user_prompt(files: list[dict], tree: str, focus: str = None) -> str:
    context = build_context(files)
    focus_block = f"\n\n**Focus area**: {focus}\nPrioritize fixes related to this area." if focus else ""

    return f"""Analyze this code and provide surgical fixes:

## File Tree
{tree}

## Source Code (line-numbered)
{context}
{focus_block}

Provide your fixes using <<<WRITE>>> and <<<PATCH>>> blocks. Be precise with line numbers.
End with a ## Summary of all changes."""


def build_summary_report(
    repo_name: str, files: list[dict], blocks: list[dict],
    results: list[dict], llm_output: str, clone_path: str, focus: str = None
) -> str:
    applied = [r for r in results if r["status"] == "applied"]
    skipped = [r for r in results if r["status"] != "applied"]

    changes_detail = ""
    for r in results:
        icon = "+" if r["status"] == "applied" else "!" if r["status"] == "error" else "~"
        changes_detail += f"  [{icon}] {r['action']:5}  {r['path']}  — {r['detail']}\n"

    return f"""# Gex Surgery Report
**Repo**: `{repo_name}`
**Clone**: `{Path(clone_path).name}/`
**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Model**: `{PROVIDER}/{MODEL}`
**Files Scanned**: {len(files)}
**Patches Applied**: {len(applied)} / {len(results)}
{f'**Focus**: {focus}' if focus else ''}

---

## Changes Applied

{changes_detail}

---

## LLM Analysis

{llm_output}

---
*Generated by Gex — AI Code Surgeon*
"""


def run_gex(repo_path: str, focus: str = None, focus_file: str = None, dry_run: bool = False):
    print(f"\n{'='*60}")
    print(f"  Gex — AI Code Surgeon")
    print(f"  Repo:  {repo_path}")
    print(f"  Model: {PROVIDER}/{MODEL}")
    if focus:
        print(f"  Focus: {focus}")
    if focus_file:
        print(f"  File:  {focus_file}")
    if dry_run:
        print(f"  Mode:  DRY RUN (no files modified)")
    print(f"{'='*60}\n")

    if not API_KEY:
        print("[!] AIAS_API_KEY not set.")
        sys.exit(1)

    print("[1/6] Scanning codebase...")
    files = scan_tree(repo_path, focus_file)
    print(f"       Found {len(files)} source file(s)")
    if not files:
        print("[!] No matching files found.")
        sys.exit(1)

    tree = build_tree_summary(files)

    print("[2/6] Cloning repository...")
    if dry_run:
        clone_path = None
        print("       [DRY RUN] Skipping clone")
    else:
        clone_path = clone_repo(repo_path)

    print("[3/6] Sending to LLM for analysis...")
    client = httpx.Client()
    user_prompt = build_user_prompt(files, tree, focus)

    try:
        llm_output = send_to_llm(client, GEX_SYSTEM_PROMPT, user_prompt)
    except httpx.HTTPStatusError as e:
        print(f"[!] LLM request failed: {e.response.status_code}")
        print(f"    {e.response.text[:200]}")
        sys.exit(1)

    print("[4/6] Parsing surgical blocks...")
    blocks = parse_surgical_blocks(llm_output)
    print(f"       Found {len(blocks)} surgical block(s)")

    if not blocks:
        print("       No surgical edits produced — code may already be correct.")
        print("       LLM response saved to report.")

    results = []
    if blocks and not dry_run:
        print("[5/6] Applying patches to clone...")
        results = apply_blocks_to_clone(clone_path, blocks)
    elif dry_run:
        print("[5/6] [DRY RUN] Would apply these patches:")
        for b in blocks:
            if b["action"] == "write":
                print(f"       WRITE  {b['path']}  ({len(b['content'])} chars)")
            elif b["action"] == "patch":
                print(f"       PATCH  {b['path']}  ({len(b['operations'])} ops)")
            results.append({"path": b["path"], "action": b["action"].upper(), "status": "dry_run", "detail": "not applied"})
    else:
        print("[5/6] No patches to apply.")

    print("[6/6] Generating report & workspace...")
    repo_name = Path(repo_path).resolve().name
    report = build_summary_report(repo_name, files, blocks, results, llm_output, clone_path or repo_path, focus)

    report_dir = Path(repo_path) / "reports"
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"gex_{repo_name}_{timestamp}.md"
    report_path.write_text(report)
    print(f"       Report saved: {report_path}")

    ws_name = f"Gex: {repo_name} ({datetime.now().strftime('%m/%d %H:%M')})"
    ws_result = create_workspace(client, ws_name)
    if ws_result:
        ws_id = ws_result.get("id", ws_result.get("workspace", {}).get("id", ""))
        if ws_id:
            store_in_workspace(client, ws_id, report)
            print(f"       Workspace: {ws_name}")
            print(f"       Workspace ID: {ws_id}")
        else:
            print("[!] Workspace created but no ID returned")
    else:
        print("       [!] Workspace creation failed — report saved locally only")

    client.close()

    applied = [r for r in results if r["status"] == "applied"]
    print(f"\n{'='*60}")
    print(f"  Gex surgery complete!")
    print(f"  Report:  {report_path}")
    if clone_path:
        print(f"  Clone:   {clone_path}")
    print(f"  Patches: {len(applied)} applied, {len(results) - len(applied)} skipped/errors")
    print(f"{'='*60}\n")

    return str(report_path)


def list_workspaces():
    if not API_KEY:
        print("[!] AIAS_API_KEY not set.")
        sys.exit(1)
    client = httpx.Client()
    resp = client.get(f"{API_BASE}/api/user/workspaces", headers=auth_headers)
    resp.raise_for_status()
    workspaces = resp.json()
    print(f"\n  AiAS Workspaces ({len(workspaces)} total)\n")
    for ws in workspaces:
        name = ws.get("name", "Unnamed")
        wid = ws.get("id", "?")
        mode = ws.get("mode", "?")
        print(f"  [{mode:>8}] {name}")
        print(f"            ID: {wid}")
    print()
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gex — AI Code Surgeon")
    parser.add_argument("--scan", type=str, help="Path to repo/directory to scan")
    parser.add_argument("--file", type=str, help="Focus on a specific file path")
    parser.add_argument("--focus", type=str, help="Focus area (e.g. 'fix auth bug', 'optimize queries')")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and show patches without applying")
    parser.add_argument("--list-workspaces", action="store_true", help="List AiAS workspaces")

    args = parser.parse_args()

    if args.list_workspaces:
        list_workspaces()
    elif args.scan:
        run_gex(args.scan, focus=args.focus, focus_file=args.file, dry_run=args.dry_run)
    else:
        parser.print_help()
