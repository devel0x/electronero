# split_pools.py (Windows-ready, Core 0.21+ compatible)
# Split current wallet balance into Ambassador & Governance pools on an Interchained/Bitcoin-compatible node.

import os, json, argparse
from decimal import Decimal, ROUND_DOWN, getcontext
import requests
from requests.auth import HTTPBasicAuth

getcontext().prec = 28  # safer Decimal math

# ---------- RPC Helpers ----------
def cookie_from_appdata(subdir_name):
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None, None
    path = os.path.join(appdata, subdir_name, ".cookie")
    try:
        with open(path, "r") as f:
            s = f.read().strip()
            if ":" in s:
                u, p = s.split(":", 1)
                return u, p
    except FileNotFoundError:
        pass
    return None, None

def make_rpc(args):
    user = args.rpc_user
    pw   = args.rpc_pass

    # If no explicit user/pass, try cookie auth in Windows AppData
    if not (user and pw):
        for subdir in ("Interchained", "Bitcoin"):
            u, p = cookie_from_appdata(subdir)
            if u and p:
                user, pw = u, p
                break

    def rpc_call(method, params=None):
        url = f"http://{args.rpc_host}:{args.rpc_port}/wallet/{args.wallet}" if args.wallet else f"http://{args.rpc_host}:{args.rpc_port}/"
        payload = {"jsonrpc": "1.0", "id": "splitter", "method": method, "params": params or []}
        auth = HTTPBasicAuth(user, pw) if user and pw else None
        r = requests.post(url, auth=auth, json=payload, timeout=30)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            body = r.text[:400]
            raise SystemExit(f"HTTP error calling {method}: {e}\nBody: {body}") from e
        data = r.json()
        if data.get("error"):
            raise SystemExit(f"RPC error for {method}: {data['error']}")
        return data["result"]

    return rpc_call

def validate_address(addr, RPC):
    res = RPC("validateaddress", [addr])
    if not res.get("isvalid", False):
        raise SystemExit(f"Invalid address: {addr}")

def quant8(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="Split wallet balance into Ambassador & Governance (sendmany with fee control).")
    ap.add_argument("--amb-address", required=True, help="Ambassador pool address")
    ap.add_argument("--gov-address", required=True, help="Governance pool address")
    ap.add_argument("--amb-pct", type=Decimal, default=Decimal("80"), help="Percent to Ambassadors (default 80)")
    ap.add_argument("--minconf", type=int, default=1, help="Min confirmations for spendable balance (default 1)")
    ap.add_argument("--note", default="Ambassador/Governance split", help="Wallet comment")
    ap.add_argument("--send", action="store_true", help="Broadcast the transaction (omit for dry-run)")
    ap.add_argument("--min-output", type=Decimal, default=Decimal("0.00001000"), help="Minimum allowed output amount")
    # Fee controls (choose one)
    ap.add_argument("--conf-target", type=int, default=6, help="Confirmation target in blocks (e.g., 6)")
    ap.add_argument("--fee-rate", type=Decimal, help="Absolute fee rate in ITC/kvB if your fork supports it (optional)")
    ap.add_argument("--rbf", action="store_true", help="Mark transaction replaceable (RBF)")

    # RPC params (Windows defaults)
    ap.add_argument("--rpc-host", default=os.environ.get("RPC_HOST", "127.0.0.1"))
    ap.add_argument("--rpc-port", default=os.environ.get("RPC_PORT", "8332"))
    ap.add_argument("--rpc-user", default=os.environ.get("RPC_USER"))  # cookie used if absent
    ap.add_argument("--rpc-pass", default=os.environ.get("RPC_PASS"))
    ap.add_argument("--wallet", default=os.environ.get("RPC_WALLET"))  # named wallet
    args = ap.parse_args()

    RPC = make_rpc(args)

    # Validate addresses
    validate_address(args.amb_address, RPC)
    validate_address(args.gov_address, RPC)

    # Spendable balance (trusted, not including immature/watch-only)
    bals = RPC("getbalances")
    balance = Decimal(str(bals["mine"]["trusted"]))

    if balance <= Decimal("0"):
        raise SystemExit(f"No spendable balance (trusted). Balance: {balance}")

    if not (Decimal("0") < args.amb_pct < Decimal("100")):
        raise SystemExit("--amb-pct must be between 0 and 100 (exclusive)")

    amb_amt = quant8(balance * (args.amb_pct / Decimal("100")))
    gov_amt = quant8(balance - amb_amt)

    if amb_amt < args.min_output or gov_amt < args.min_output:
        raise SystemExit(f"Outputs would be below --min-output. amb={amb_amt} gov={gov_amt} min={args.min_output}")

    outputs = {
        args.amb_address: float(amb_amt),
        args.gov_address: float(gov_amt),
    }

    # --- Estimate via PSBT for fee & change preview ---
    psbt_opts = {
        "change_type": "bech32",
        "replaceable": bool(args.rbf),
        "subtractFeeFromOutputs": [0, 1],
    }
    if args.fee_rate is not None:
        psbt_opts["fee_rate"] = float(args.fee_rate)
    else:
        psbt_opts["conf_target"] = int(args.conf_target)

    est = RPC("walletcreatefundedpsbt", [[], outputs, 0, psbt_opts, True])
    est_fee = Decimal(str(est.get("fee", "0")))
    changepos = est.get("changepos", -1)

    print("=== DRY RUN ESTIMATE ===" if not args.send else "=== ESTIMATE BEFORE SEND ===")
    print(f"Trusted spendable balance: {balance}")
    print(f"Ambassador %: {args.amb_pct}%  -> {amb_amt}")
    print(f"Governance %: {Decimal('100') - args.amb_pct}% -> {gov_amt}")
    print(f"Estimated fee: {est_fee}  ChangePos: {changepos}")
    print("Planned outputs:", json.dumps(outputs, indent=2))
    print(f"RBF: {bool(args.rbf)}  Change type: bech32  Fee control: {'fee_rate='+str(args.fee_rate) if args.fee_rate is not None else 'conf_target='+str(args.conf_target)}")

    if not args.send:
        print("\n(No broadcast. Add --send to actually send.)")
        return

    # --- Broadcast with sendmany (mirrors estimate) ---
    # --- Broadcast with sendmany (fork expects array for 'subtract fee from outputs') ---
    # subtract_from = [args.amb_address, args.gov_address]  # take fee from both
    # params = ["", outputs, args.minconf, args.note, subtract_from, bool(args.rbf), int(args.conf_target)]
    # Optional: add estimate_mode string as last arg, e.g. "CONSERVATIVE"
    # params.append("CONSERVATIVE")
    # txid = RPC("sendmany", params)
    # --- Estimate via PSBT for fee & change preview ---
    psbt_opts = {
        "change_type": "bech32",
        "replaceable": bool(args.rbf),
        "subtractFeeFromOutputs": [0, 1],  # subtract from both outputs
    }
    if args.fee_rate is not None:
        psbt_opts["feeRate"] = float(args.fee_rate)  # <-- camelCase, not fee_rate
    else:
        psbt_opts["conf_target"] = int(args.conf_target)

    est = RPC("walletcreatefundedpsbt", [[], outputs, 0, psbt_opts, True])
    est_fee = Decimal(str(est.get("fee", "0")))
    changepos = est.get("changepos", -1)

    print("=== ESTIMATE BEFORE SEND ===")
    print(f"Trusted spendable balance: {balance}")
    print(f"Ambassador %: {args.amb_pct}%  -> {amb_amt}")
    print(f"Governance %: {Decimal('100') - args.amb_pct}% -> {gov_amt}")
    print(f"Estimated fee: {est_fee}  ChangePos: {changepos}")
    print("Planned outputs:", json.dumps(outputs, indent=2))
    print(f"RBF: {bool(args.rbf)}  Change type: bech32  Fee control: "
          f"{'feeRate='+str(args.fee_rate) if args.fee_rate is not None else 'conf_target='+str(args.conf_target)}")

    if not args.send:
        print("\n(No broadcast. Add --send to actually send.)")
        return

    # --- PSBT sign + finalize + broadcast (honors feeRate exactly) ---
    psbt = est["psbt"]

    proc = RPC("walletprocesspsbt", [psbt, True, "ALL", True])  # sign=True, bip32derivs=True
    signed_psbt = proc["psbt"]

    fin = RPC("finalizepsbt", [signed_psbt])
    if not fin.get("complete", False):
        raise SystemExit("PSBT not complete; cannot finalize")
    rawtx = fin["hex"]

    # Optional: sanity check feerate before broadcast
    # dec = RPC("decoderawtransaction", [rawtx])
    # print("vsize:", dec["vsize"])

    txid = RPC("sendrawtransaction", [rawtx])
    print(f"Broadcasted TXID: {txid}")
    print(f"Broadcasted TXID: {txid}")

if __name__ == "__main__":
    main()
