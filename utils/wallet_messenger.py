import os
import json
import sys
import time
from typing import List, Dict, Any

MESSAGE_DIR = os.environ.get("MESSAGE_DIR", os.path.join(os.path.dirname(__file__), "messages"))


def _msg_file(address: str) -> str:
    return os.path.join(MESSAGE_DIR, f"{address}.json")


def _load_messages(address: str) -> List[Dict[str, Any]]:
    path = _msg_file(address)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_messages(address: str, msgs: List[Dict[str, Any]]) -> None:
    os.makedirs(MESSAGE_DIR, exist_ok=True)
    path = _msg_file(address)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msgs, f, indent=2)


def send_message(to_addr: str, from_addr: str, subject: str, body: str) -> int:
    """Send a message from from_addr to to_addr."""
    msgs = _load_messages(to_addr)
    next_id = max([m.get("id", 0) for m in msgs], default=0) + 1
    msg = {
        "id": next_id,
        "from": from_addr,
        "subject": subject,
        "message": body,
        "timestamp": int(time.time()),
    }
    msgs.append(msg)
    _save_messages(to_addr, msgs)
    return next_id


def list_messages(address: str) -> List[Dict[str, Any]]:
    """Return list of messages for address."""
    return _load_messages(address)


def read_message(address: str, key: str) -> Dict[str, Any]:
    """Read a single message by id or subject."""
    msgs = _load_messages(address)
    for m in msgs:
        if str(m.get("id")) == str(key) or m.get("subject") == key:
            return m
    raise KeyError("Message not found")


def _cli_list(address: str) -> None:
    msgs = list_messages(address)
    for m in msgs:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m["timestamp"]))
        print(f"[{m['id']}] {m['subject']} from {m['from']} at {ts}")
        print(m['message'])
        print()


def _cli_read(address: str, key: str) -> None:
    try:
        m = read_message(address, key)
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(m["timestamp"]))
        print(json.dumps({**m, "timestamp": ts}, indent=2))
    except KeyError:
        print("Message not found")


def _cli_send(to_addr: str, from_addr: str, subject: str, body_parts: List[str]) -> None:
    body = " ".join(body_parts)
    msg_id = send_message(to_addr, from_addr, subject, body)
    print(f"Sent message {msg_id} to {to_addr}")


def main(argv: List[str]) -> None:
    if not argv:
        print("Usage: wallet_messenger.py [send|list|read] ...")
        return
    cmd = argv[0]
    if cmd == "send" and len(argv) >= 5:
        _cli_send(argv[1], argv[2], argv[3], argv[4:])
    elif cmd == "list" and len(argv) == 2:
        _cli_list(argv[1])
    elif cmd == "read" and len(argv) == 3:
        _cli_read(argv[1], argv[2])
    else:
        print("Usage:")
        print("  wallet_messenger.py send <to> <from> <subject> <message>")
        print("  wallet_messenger.py list <address>")
        print("  wallet_messenger.py read <address> <id|subject>")


if __name__ == "__main__":
    main(sys.argv[1:])
