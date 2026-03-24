#!/usr/bin/env python3
"""
AiAS Code Analysis Buddy
Scans a codebase, sends findings to AiAS via API key auth,
stores results in workspaces for persistent cloud storage.
Outputs markdown reports.

Usage:
  python analyzer.py --scan ./path/to/repo
  python analyzer.py --scan ./path/to/repo --focus "auth bug"
  python analyzer.py --scan ./path/to/repo --file api/routes/auth.py
  python analyzer.py --list-workspaces
"""

import os
import sys
import json
import hashlib
import argparse
import httpx
from pathlib import Path
from datetime import datetime

API_BASE = os.getenv("AIAS_API_URL", "https://api.aiassist.net")
API_KEY = os.getenv("AIAS_API_KEY", "aai_08Yje_4t11_r4zxMMxOWymYht5pbx2ASvRwJB0wKasc")
MODEL = os.getenv("AIAS_MODEL", "llama-3.3-70b-versatile")
PROVIDER = os.getenv("AIAS_PROVIDER", "groq")

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", ".next", ".cache", "appendonlydir",
    "redis-data", ".local", ".replit", ".upm",
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

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
if PROVIDER:
    headers["X-AiAssist-Provider"] = PROVIDER


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
                content = "\n".join(lines[:max_lines]) + f"\n\n# ... truncated ({len(lines) - max_lines} more lines, {size} bytes total)"
            files.append({"path": rel, "size": size, "content": content, "lines": content.count("\n") + 1})
        except Exception as e:
            files.append({"path": rel, "error": str(e)})

    return files


def build_context(files: list[dict], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    parts = []
    total = 0
    for f in files:
        content = f.get("content", f.get("error", ""))
        header = f"### {f['path']} ({f.get('lines', '?')} lines)\n"
        block = f"```\n{content}\n```\n"
        chunk = header + block
        if total + len(chunk) > max_chars:
            parts.append(f"### {f['path']}\n[truncated: context limit reached]\n")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)


def build_tree_summary(files: list[dict]) -> str:
    lines = [f"  {f['path']}  ({f.get('lines', '?')} lines, {f.get('size', 0)} bytes)" for f in files]
    return "\n".join(lines)


def create_workspace(client: httpx.Client, name: str) -> dict:
    resp = client.post(f"{API_BASE}/api/workspaces", json={
        "initial_message": f"Code analysis workspace: {name}",
        "client_id": f"analyzer_{hashlib.md5(name.encode()).hexdigest()[:12]}",
    }, headers=headers, timeout=30)
    if resp.status_code == 401:
        print("[!] API key auth failed for workspace creation. Check your AIAS_API_KEY.")
        return None
    resp.raise_for_status()
    return resp.json()


def send_to_llm(client: httpx.Client, system_prompt: str, user_msg: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 16384,
    }
    resp = client.post(
        f"{API_BASE}/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"] or ""
    if not content.strip():
        print(f"[!] LLM returned empty content. Full response:")
        print(json.dumps(data, indent=2)[:2000])
    return content


def store_in_workspace(client: httpx.Client, workspace_id: str, content: str):
    resp = client.post(
        f"{API_BASE}/api/workspaces/{workspace_id}/messages",
        json={"content": content},
        headers=headers,
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[!] Failed to store message in workspace: {resp.status_code}")


def run_analysis(repo_path: str, focus: str = None, focus_file: str = None):
    print(f"\n{'='*60}")
    print(f"  AiAS Code Analysis Buddy")
    print(f"  Repo:  {repo_path}")
    print(f"  Model: {PROVIDER}/{MODEL}")
    if focus:
        print(f"  Focus: {focus}")
    if focus_file:
        print(f"  File:  {focus_file}")
    print(f"{'='*60}\n")

    if not API_KEY:
        print("[!] AIAS_API_KEY not set. Set it to your aai_ key.")
        print("    export AIAS_API_KEY=aai_your_key_here")
        sys.exit(1)

    print("[1/4] Scanning codebase...")
    files = scan_tree(repo_path, focus_file)
    print(f"       Found {len(files)} source files")

    tree = build_tree_summary(files)
    context = build_context(files)

    system_prompt = """You are an expert code analysis assistant. You review codebases and provide:
1. **Architecture Overview** — how the project is structured
2. **Potential Bugs** — real issues with file paths and line references
3. **Security Concerns** — auth, injection, secrets, encryption gaps
4. **Performance Issues** — N+1 queries, unnecessary loops, memory leaks
5. **Code Quality** — naming, duplication, missing error handling
6. **Suggested Fixes** — concrete code changes (do NOT rewrite entire files, show surgical diffs)

Always reference exact file paths. Be specific, not generic. If something looks fine, say so."""

    focus_instruction = ""
    if focus:
        focus_instruction = f"\n\n**Special focus area**: {focus}\nPrioritize analysis related to this area."

    user_msg = f"""Analyze this codebase:

## File Tree
{tree}

## Source Code
{context}
{focus_instruction}

Provide a thorough analysis with specific file paths and line references. Format as markdown."""

    print("[2/4] Sending to LLM for analysis...")
    client = httpx.Client()

    try:
        analysis = send_to_llm(client, system_prompt, user_msg)
    except httpx.HTTPStatusError as e:
        print(f"[!] LLM request failed: {e.response.status_code}")
        print(f"    {e.response.text[:200]}")
        sys.exit(1)

    print("[3/4] Generating report...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_name = Path(repo_path).resolve().name
    report_name = f"analysis_{repo_name}_{timestamp}.md"
    report_dir = Path(repo_path) / "reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / report_name

    report = f"""# Code Analysis Report
**Repo**: `{repo_name}`
**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Model**: `{PROVIDER}/{MODEL}`
**Files Scanned**: {len(files)}
{f'**Focus**: {focus}' if focus else ''}
{f'**File Filter**: {focus_file}' if focus_file else ''}

---

{analysis}

---
*Generated by AiAS Code Analysis Buddy*
"""

    report_path.write_text(report)
    print(f"       Report saved: {report_path}")

    print("[4/4] Storing in AiAS workspace...")
    ws_name = f"CodeScan: {repo_name} ({datetime.now().strftime('%m/%d %H:%M')})"
    ws_result = create_workspace(client, ws_name)
    if ws_result:
        ws_id = ws_result.get("id", ws_result.get("workspace", {}).get("id", ""))
        if ws_id:
            store_in_workspace(client, ws_id, analysis)
            print(f"       Workspace created: {ws_name}")
            print(f"       Workspace ID: {ws_id}")
        else:
            print(f"[!] Workspace created but no ID returned")
    else:
        print("       [!] Workspace creation failed — report saved locally only")

    client.close()

    print(f"\n{'='*60}")
    print(f"  Analysis complete!")
    print(f"  Report: {report_path}")
    print(f"{'='*60}\n")

    return str(report_path)


def list_workspaces():
    if not API_KEY:
        print("[!] AIAS_API_KEY not set.")
        sys.exit(1)

    client = httpx.Client()
    resp = client.get(
        f"{API_BASE}/api/user/workspaces",
        headers=headers,
    )
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
    parser = argparse.ArgumentParser(description="AiAS Code Analysis Buddy")
    parser.add_argument("--scan", type=str, help="Path to repo to scan")
    parser.add_argument("--focus", type=str, help="Focus area (e.g. 'authentication bug', 'performance')")
    parser.add_argument("--file", type=str, help="Filter to specific file path")
    parser.add_argument("--list-workspaces", action="store_true", help="List all AiAS workspaces")

    args = parser.parse_args()

    if args.list_workspaces:
        list_workspaces()
    elif args.scan:
        run_analysis(args.scan, focus=args.focus, focus_file=args.file)
    else:
        parser.print_help()
