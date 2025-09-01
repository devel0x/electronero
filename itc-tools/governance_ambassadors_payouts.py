#!/usr/bin/env python3
# distribute_ambassadors.py
# Distribute Ambassador pool across many addresses via PSBT (walletcreatefundedpsbt -> walletprocesspsbt -> finalizepsbt -> sendrawtransaction)
# Core 0.21+ compatible (Interchained/Bitcoin). Windows-friendly with cookie auth fallback.

import os, csv, json, argparse
from decimal import Decimal, ROUND_DOWN, getcontext
from pathlib import Path
from collections import OrderedDict
import requests
from requests.auth import HTTPBasicAuth

getcontext().prec = 28

# ---------------- RPC helpers ----------------
def cookie_from_appdata(subdir):
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None, None
    p = os.path.join(appdata, subdir, ".cookie")
    try:
        with open(p, "r", encoding="utf-8") as f:
            s = f.read().strip()
            if ":" in s:
                u, pw = s.split(":", 1)
                return u, pw
    except FileNotFoundError:
        pass
    return None, None

def make_rpc(args):
    user, pw = args.rpc_user, args.rpc_pass
    if not (user and pw):
        # Windows cookie auth fallback
        for subdir in ("Interchained", "Bitcoin"):
            u, p = cookie_from_appdata(subdir)
            if u and p:
                user, pw = u, p
                break

    def RPC(method, params=None):
        base = f"http://{args.rpc_host}:{args.rpc_port}"
        url = f"{base}/wallet/{args.wallet}" if args.wallet else f"{base}/"
        payload = {"jsonrpc":"1.0","id":"ambdist","method":method,"params": params or []}
        auth = HTTPBasicAuth(user, pw) if user and pw else None
        r = requests.post(url, auth=auth, json=payload, timeout=60)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise SystemExit(f"HTTP error calling {method}: {e}\nBody: {r.text[:400]}") from e
        data = r.json()
        if data.get("error"):
            raise SystemExit(f"RPC error for {method}: {data['error']}")
        return data["result"]
    return RPC

def validate_address(addr, RPC):
    res = RPC("validateaddress", [addr])
    if not res.get("isvalid", False):
        raise SystemExit(f"Invalid address: {addr}")

# ---------------- Math / helpers ----------------
def quant8(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

def chunk_list(lst, size):
    if size <= 0:
        yield lst
        return
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

# ---------------- CSV / JSON loaders ----------------
def load_recipients_from_csv(path: Path):
    rec = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 2: continue
            a, s = row[0].strip(), row[1].strip()
            if not a or not s or a.lower().startswith("address"): continue
            rec.append((a, Decimal(s)))
    if not rec:
        raise SystemExit("No recipients parsed from CSV. Need two columns: address,share")
    return rec

def load_recipients_from_json(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = []
    for item in data:
        rec.append((item["address"], Decimal(str(item["share"]))))
    if not rec:
        raise SystemExit("JSON recipients list is empty.")
    return rec

# ---------------- Distribution logic ----------------
def normalize_shares(pairs):
    weights = []
    for addr, share in pairs:
        w = max(Decimal("0"), share)
        weights.append((addr, w))
    total_w = sum(w for _, w in weights)
    if total_w <= 0:
        raise SystemExit("Sum of shares/weights is zero.")
    return weights, total_w

def build_outputs_ordered(weights, total_weight, total_amount, RPC, dust_threshold=Decimal("0.00000546")):
    """
    Returns a *list* of (addr, float_amount) to preserve order for subtractFeeFromOutputs indices.
    """
    out_list = []
    for addr, w in weights:
        amt = quant8(total_amount * (w / total_weight))
        if amt <= dust_threshold:
            continue  # skip dust
        validate_address(addr, RPC)
        out_list.append((addr, float(amt)))
    if not out_list:
        raise SystemExit("All computed outputs were dust or invalid. Adjust shares/amounts.")
    return out_list

# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser(description="Distribute Ambassador pool via PSBT (recommended) with batching & feeRate.")
    ap.add_argument("--csv", type=str, help="CSV file with 'address,share'")
    ap.add_argument("--json", type=str, help="JSON list of {address, share}")
    ap.add_argument("--total-amount", type=Decimal, help="Total amount to distribute, e.g. 123.45678901")
    ap.add_argument("--use-balance", action="store_true", help="Use wallet trusted balance as total amount")
    ap.add_argument("--minconf", type=int, default=1, help="Min confirmations for spendable balance (default 1)")
    ap.add_argument("--comment", default="Ambassador distribution", help="Human note (logged in wallet)")
    ap.add_argument("--send", action="store_true", help="Broadcast the transaction(s); default is dry-run")
    ap.add_argument("--batch-size", type=int, default=0, help="Max recipients per tx (0 = all in one)")
    ap.add_argument("--rbf", action="store_true", help="Mark txs replaceable (BIP125)")
    ap.add_argument("--fee-rate", type=Decimal, help="Absolute feeRate per kB (e.g., 0.00015). If unset, conf_target is used.")
    ap.add_argument("--conf-target", type=int, default=6, help="Conf target blocks (used if --fee-rate not set)")
    ap.add_argument("--min-output", type=Decimal, default=Decimal("0.00001000"), help="Minimum recipient output amount")
    # RPC
    ap.add_argument("--rpc-host", default=os.getenv("RPC_HOST","127.0.0.1"))
    ap.add_argument("--rpc-port", default=os.getenv("RPC_PORT","8332"))
    ap.add_argument("--rpc-user", default=os.getenv("RPC_USER"))
    ap.add_argument("--rpc-pass", default=os.getenv("RPC_PASS"))
    ap.add_argument("--wallet", default=os.getenv("RPC_WALLET"))  # e.g., ambassador_pool
    args = ap.parse_args()

    if not args.csv and not args.json:
        raise SystemExit("Provide --csv or --json")

    RPC = make_rpc(args)

    # Load recipients
    recipients = load_recipients_from_csv(Path(args.csv)) if args.csv else load_recipients_from_json(Path(args.json))

    # Determine total amount
    if args.total_amount and args.use_balance:
        raise SystemExit("Use either --total-amount or --use-balance, not both.")
    if args.total_amount:
        total_amount = quant8(args.total_amount)
    elif args.use_balance:
        # Use trusted spendable only
        bals = RPC("getbalances")
        bal = Decimal(str(bals["mine"]["trusted"]))
        if bal <= 0:
            raise SystemExit(f"No spendable balance (trusted, ≥{args.minconf} conf). Balance: {bal}")
        total_amount = quant8(bal)
    else:
        raise SystemExit("You must specify --total-amount or --use-balance.")

    # Normalize & build ordered outputs
    weights, total_w = normalize_shares(recipients)
    out_list = build_outputs_ordered(weights, total_w, total_amount, RPC, dust_threshold=args.min_output)

    # Batching
    batches = list(chunk_list(out_list, args.batch_size if args.batch_size and args.batch_size > 0 else len(out_list)))

    # Summary
    print("=== Ambassador Distribution (PSBT) ===")
    print(f"Recipients parsed: {len(recipients)}  |  Valid (after dust filter): {sum(len(b) for b in batches)}")
    print(f"Total to distribute: {total_amount}")
    print("(Fee paid from change; recipients receive their full amounts)")

    txids = []
    for i, batch in enumerate(batches, 1):
        # Maintain output order (addr -> amt) for PSBT; indices 0..n-1 will be fee-subtracted
        outputs_dict = OrderedDict((addr, amt) for addr, amt in batch)
        # subtract_idx = list(range(len(batch)))  # subtract fee from all outputs (pro-rata)
        # before: subtract from all outputs
        # subtract_idx = list(range(len(batch)))

        # after: for big batches, don't subtract from recipients at all
        subtract_idx = []  # fee comes from the wallet's change, not from recipients
        psbt_opts = {
            "change_type": "bech32",
            "replaceable": bool(args.rbf),
            "subtractFeeFromOutputs": subtract_idx,   # <= empty list bypasses the 32 cap
        }
        # keep using feeRate (camelCase) or conf_target:
        if args.fee_rate is not None:
            psbt_opts["feeRate"] = float(args.fee_rate)
        else:
            psbt_opts["conf_target"] = int(args.conf_target)

        # # PSBT options
        # psbt_opts = {
        #     "change_type": "bech32",
        #     "replaceable": bool(args.rbf),
        #     "subtractFeeFromOutputs": subtract_idx,
        # }
        # if args.fee_rate is not None:
        #     psbt_opts["feeRate"] = float(args.fee_rate)  # <-- camelCase is required
        # else:
        #     psbt_opts["conf_target"] = int(args.conf_target)

        # Create PSBT (estimate)
        est = RPC("walletcreatefundedpsbt", [[], outputs_dict, 0, psbt_opts, True])
        est_fee = Decimal(str(est.get("fee", "0")))
        changepos = est.get("changepos", -1)

        print(f"\n--- Batch {i}/{len(batches)}: {len(batch)} recipients ---")
        for addr, amt in batch[:5]:
            print(f"{addr}: {amt}")
        if len(batch) > 5:
            print(f"... and {len(batch)-5} more")
        print(f"Estimated fee: {est_fee}   ChangePos: {changepos}   RBF: {args.rbf}   Fee control: "
              f"{'feeRate='+str(args.fee_rate) if args.fee_rate is not None else 'conf_target='+str(args.conf_target)}")

        if not args.send:
            continue

        # Sign -> finalize -> broadcast
        psbt = est["psbt"]
        proc = RPC("walletprocesspsbt", [psbt, True, "ALL", True])  # sign=True, bip32derivs=True
        signed_psbt = proc["psbt"]

        fin = RPC("finalizepsbt", [signed_psbt])
        if not fin.get("complete", False):
            raise SystemExit("PSBT not complete; cannot finalize (check keys/UTXOs).")
        rawtx = fin["hex"]

        # Optional safety: ensure our feerate >= mempool min
        # minfee = Decimal(str(RPC("getmempoolinfo")["mempoolminfee"]))
        # (You can enforce a floor here if desired.)

        txid = RPC("sendrawtransaction", [rawtx])
        print(f"Broadcasted batch {i}/{len(batches)} TXID: {txid}")
        txids.append(txid)

    if not args.send:
        print("\nDRY RUN complete. Add --send to broadcast.")
    else:
        print("\nAll transactions broadcast.")
        print("TXIDs:", txids)

if __name__ == "__main__":
    main()
