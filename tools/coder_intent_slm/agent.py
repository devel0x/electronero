"""Intent router agent for coding automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from model import TinyIntentModel
from plugins import HttpToolPlugin, ShellPlugin, WebSearchPlugin

TRAINING_SAMPLES = [
    ("code_generation", "write a python function for parsing json"),
    ("code_generation", "generate rust code to compute sha256"),
    ("debugging", "why does my unit test fail with null pointer"),
    ("debugging", "fix this stack trace in c plus plus"),
    ("refactor", "refactor this class into smaller modules"),
    ("refactor", "improve code readability and rename functions"),
    ("internet_lookup", "search latest docs for fastapi dependency injection"),
    ("internet_lookup", "find api reference online for postgres jsonb"),
    ("run_command", "run git status"),
    ("run_command", "execute python -m pytest"),
]


@dataclass
class CodingAutomationAgent:
    model: TinyIntentModel = field(default_factory=TinyIntentModel)

    def __post_init__(self) -> None:
        self.model.fit(TRAINING_SAMPLES)
        self.plugins = {
            "shell": ShellPlugin(),
            "web_search": WebSearchPlugin(),
            "http_tool": HttpToolPlugin(),
        }

    def infer_intent(self, user_text: str) -> dict[str, Any]:
        pred = self.model.predict(user_text)
        return {
            "intent": pred.intent,
            "confidence": round(pred.confidence, 4),
            "scores": {k: round(v, 4) for k, v in pred.scores.items()},
        }

    def handle(self, user_text: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        pred = self.model.predict(user_text)

        if pred.intent == "run_command":
            plugin_name = "shell"
            result = self.plugins[plugin_name].run(payload.get("command", ""))
        elif pred.intent == "internet_lookup":
            plugin_name = payload.get("plugin", "web_search")
            query = payload.get("query", user_text)
            result = self.plugins[plugin_name].run(query)
        else:
            plugin_name = "none"
            result = {
                "ok": True,
                "action": "plan_only",
                "message": (
                    "Intent detected but no direct execution needed. "
                    "Use this intent to route into your code generation/debug pipeline."
                ),
            }

        return {
            "intent": pred.intent,
            "confidence": round(pred.confidence, 4),
            "plugin": plugin_name,
            "result": result,
        }
