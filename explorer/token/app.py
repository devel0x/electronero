import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask, jsonify, request, render_template, url_for
from modules.python.electronero import WalletRPC, RPCError

WALLET_HOST = os.environ.get("WALLET_HOST", "127.0.0.1")
WALLET_PORT = int(os.environ.get("WALLET_PORT", "18082"))

wallet = WalletRPC(host=WALLET_HOST, port=WALLET_PORT)
app = Flask(__name__, template_folder="templates", static_folder="static")

@app.route('/')
def index():
    tokens = []
    error = None
    try:
        res = wallet.call("all_tokens")
        all_tokens = res.get("tokens", []) if isinstance(res, dict) else res
        for entry in all_tokens:
            addr = entry.get("address")
            try:
                info = wallet.call("token_info", {"token_address": addr})
            except RPCError:
                info = {}
            tokens.append({
                "name": entry.get("name"),
                "symbol": entry.get("symbol"),
                "address": addr,
                "supply": info.get("supply", entry.get("supply")),
                "creator_fee": info.get("creator_fee")
            })
    except RPCError as e:
        error = str(e)
    return render_template('index.html', tokens=tokens, error=error)

@app.route('/token/<token_addr>')
def token_history(token_addr: str):
    params = {"token_address": token_addr}
    address = request.args.get("address")
    if address:
        params["address"] = address
    typ = request.args.get("type", "")
    if typ:
        params["type"] = typ
    try:
        result = wallet.call("token_history", params)
    except RPCError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@app.route('/token')
def token_history_html():
    token_addr = request.args.get("token")
    if not token_addr:
        return render_template("results.html", title="Token History", error="Missing token address", history=[])
    address = request.args.get("address")
    typ = request.args.get("type")
    params = {"token_address": token_addr}
    if address:
        params["address"] = address
    if typ:
        params["type"] = typ
    try:
        result = wallet.call("token_history", params)
        if isinstance(result, dict):
            history = result.get("history") or result.get("transfers") or []
        else:
            history = result
    except RPCError as e:
        return render_template("results.html", title="Token History", error=str(e), history=[])
    return render_template("results.html", title="Token History", history=history, error=None)

@app.route('/address/<addr>')
def address_history(addr: str):
    params = {"address": addr}
    typ = request.args.get("type", "")
    if typ:
        params["type"] = typ
    try:
        result = wallet.call("token_history_addr", params)
    except RPCError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


@app.route('/address')
def address_history_html():
    addr = request.args.get("addr")
    if not addr:
        return render_template("results.html", title="Address History", error="Missing address", history=[])
    typ = request.args.get("type")
    params = {"address": addr}
    if typ:
        params["type"] = typ
    try:
        result = wallet.call("token_history_addr", params)
        if isinstance(result, dict):
            history = result.get("history") or result.get("transfers") or []
        else:
            history = result
    except RPCError as e:
        return render_template("results.html", title="Address History", error=str(e), history=[])
    return render_template("results.html", title="Address History", history=history, error=None)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
