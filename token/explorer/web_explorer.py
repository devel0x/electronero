#!/usr/bin/env python3
"""Web-based token explorer using Flask.

This lightweight front end allows searching for a token's history
and filtering results by address. It reuses the same ``token_history``
RPC call used by ``token_explorer.py`` and displays results in an HTML
table.
"""

from __future__ import annotations

import argparse
import base64
import json
from http.client import HTTPConnection
from typing import List, Optional

from flask import Flask, render_template_string, request


class RPCClient:
    """Minimal JSON-RPC client."""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        auth = f"{user}:{password}".encode()
        self.authhdr = b"Basic " + base64.b64encode(auth)
        self.conn = HTTPConnection(host, port=port, timeout=30)

    def call(self, method: str, params: Optional[List] = None):
        if params is None:
            params = []
        obj = {
            "jsonrpc": "1.0",
            "id": "token-explorer",
            "method": method,
            "params": params,
        }
        self.conn.request(
            "POST",
            "/",
            json.dumps(obj),
            {"Authorization": self.authhdr, "Content-type": "application/json"},
        )
        resp = self.conn.getresponse()
        if resp is None:
            raise ConnectionError("no response from RPC server")
        body = resp.read().decode()
        reply = json.loads(body)
        if reply.get("error"):
            raise RuntimeError(reply["error"])
        return reply["result"]


def make_app(rpc: RPCClient) -> Flask:
    app = Flask(__name__)

    TEMPLATE = """
    <!doctype html>
    <title>Token Explorer</title>
    <h1>Token Explorer</h1>
    <form method="get">
      <label>Token: <input name="token" value="{{ token|default('') }}"></label>
      <label>Address filter: <input name="address" value="{{ address|default('') }}"></label>
      <input type="submit" value="Search">
    </form>
    {% if history %}
    <table border="1" cellspacing="0" cellpadding="4">
      <tr><th>OP</th><th>FROM</th><th>TO</th><th>AMOUNT</th><th>MEMO</th></tr>
      {% for e in history %}
      <tr>
        <td>{{ e.op }}</td>
        <td>{{ e.from }}</td>
        <td>{{ e.to }}</td>
        <td>{{ e.amount }}</td>
        <td>{{ e.memo }}</td>
      </tr>
      {% endfor %}
    </table>
    {% endif %}
    """

    @app.route("/", methods=["GET"])
    def index():
        token = request.args.get("token")
        address = request.args.get("address")
        history = None
        if token:
            params = [token]
            if address:
                params.append(address)
            history = rpc.call("token_history", params)
        return render_template_string(TEMPLATE, token=token, address=address, history=history)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run web token explorer")
    parser.add_argument("--rpchost", default="127.0.0.1")
    parser.add_argument("--rpcport", default=8332, type=int)
    parser.add_argument("--rpcuser", required=True)
    parser.add_argument("--rpcpassword", required=True)
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", default=5000, type=int)
    args = parser.parse_args()

    rpc = RPCClient(args.rpchost, args.rpcport, args.rpcuser, args.rpcpassword)
    app = make_app(rpc)
    app.run(host=args.listen, port=args.port)


if __name__ == "__main__":
    main()
