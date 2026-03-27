"""Plugin interfaces and built-in plugins for coding automation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import shlex
import subprocess
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Plugin(Protocol):
    name: str

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        ...


@dataclass
class ShellPlugin:
    """Executes safe shell commands for local coding tasks."""

    name: str = "shell"
    timeout_seconds: int = 15

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        allowed_prefixes = tuple(kwargs.get("allowed_prefixes", ["git", "python", "cmake", "make", "rg"]))
        parts = shlex.split(query)
        if not parts:
            return {"ok": False, "error": "Empty command."}
        if parts[0] not in allowed_prefixes:
            return {"ok": False, "error": f"Command '{parts[0]}' is not allowed."}

        proc = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }


@dataclass
class WebSearchPlugin:
    """Search the public web with DuckDuckGo instant answer endpoint."""

    name: str = "web_search"

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        params = urlencode({"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        url = f"https://api.duckduckgo.com/?{params}"
        req = Request(url, headers={"User-Agent": "coder-intent-slm/0.1"})
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))

        related = payload.get("RelatedTopics", [])
        hits = []
        for entry in related[:5]:
            if isinstance(entry, dict) and "Text" in entry:
                hits.append({"title": entry.get("Text", ""), "url": entry.get("FirstURL", "")})

        return {
            "ok": True,
            "abstract": payload.get("AbstractText", ""),
            "results": hits,
        }


@dataclass
class HttpToolPlugin:
    """General internet plugin: fetch JSON from any HTTP endpoint."""

    name: str = "http_tool"

    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        # query is expected to be URL
        req = Request(query, headers={"User-Agent": "coder-intent-slm/0.1"})
        with urlopen(req, timeout=15) as resp:  # noqa: S310
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")

        parsed: Any
        if "json" in content_type:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body[:2000]}
        else:
            parsed = {"raw": body[:2000]}

        return {"ok": True, "content_type": content_type, "data": parsed}
