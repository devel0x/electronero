"""CLI entrypoint for the coding automation SLM."""

from __future__ import annotations

import argparse
import json

from agent import CodingAutomationAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coder-intent-slm",
        description=(
            "Tiny standalone intent-focused language model for coding automation. "
            "Can route to shell and internet plugins."
        ),
    )
    parser.add_argument("prompt", help="Natural language request.")
    parser.add_argument("--command", help="Shell command payload for run_command intents.")
    parser.add_argument("--query", help="Query/URL payload for internet intents.")
    parser.add_argument(
        "--plugin",
        choices=["web_search", "http_tool"],
        default="web_search",
        help="Internet plugin used when intent is internet_lookup.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = CodingAutomationAgent()
    payload = {"command": args.command, "query": args.query, "plugin": args.plugin}
    out = agent.handle(args.prompt, payload=payload)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
