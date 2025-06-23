#!/usr/bin/env python3
"""Display the current Electronero daemon block height."""

from __future__ import annotations

import argparse
import sys

from electronero import DaemonRPC


def main() -> int:
    parser = argparse.ArgumentParser(description="Show Electronero daemon block height")
    parser.add_argument("--host", default="127.0.0.1", help="RPC host")
    parser.add_argument("--port", type=int, default=12090, help="RPC port")
    args = parser.parse_args()

    rpc = DaemonRPC(host=args.host, port=args.port)
    try:
        height = rpc.get_block_count()
    except Exception as exc:  # broad catch for simplicity
        print(f"Failed to fetch height: {exc}", file=sys.stderr)
        return 1

    print(height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
