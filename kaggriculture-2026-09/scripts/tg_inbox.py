#!/usr/bin/env python
"""Two-way Telegram channel: capture messages the user sends to the bot.

`push_live.py` only ever calls `sendMessage` (and one `getUpdates` at first-run setup to
resolve the chat id), so everything the user typed into the bot was invisible to this
project. This script adds the missing inbound half.

It long-polls `getUpdates` with a persisted offset and appends every message from the
configured chat to `data/tg-inbox.jsonl`, one JSON object per line:

    {"utc": "...", "update_id": 123, "from": "nickyl", "text": "...", "seen": false}

The agent reads that file to see what the user sent. Each captured message is acknowledged
back to the chat so the user knows it landed.

Run:   .venv/bin/python scripts/tg_inbox.py          (foreground loop)
       bash -c 'while true; do .venv/bin/python scripts/tg_inbox.py; sleep 5; done'   (supervised)
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "data" / "telegram.json"
OFFSET = ROOT / "data" / "tg-offset.json"
INBOX = ROOT / "data" / "tg-inbox.jsonl"
POLL_TIMEOUT = 25          # seconds of long-poll; keeps the loop responsive without busy-wait
BACKOFF_MAX = 60

# Messages containing any of these trigger an immediate live status push, so the channel is
# useful without waiting for the agent to wake up and read the inbox. The agent is NOT a
# daemon: it only reads data/tg-inbox.jsonl during one of its own turns, so anything that
# needs an immediate answer must be handled here.
STATUS_WORDS = ("排名", "状态", "榜单", "多少分", "几分", "status", "rank", "看下telegram",
                "看一下telegram", "查一下", "score")


def tg(method, token, **kw):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(kw).encode() if kw else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 15) as r:
        return json.load(r)


def load_cfg():
    cfg = json.loads(CFG.read_text())
    if not cfg.get("token"):
        raise SystemExit("data/telegram.json has no token")
    return cfg


def load_offset():
    if OFFSET.exists():
        try:
            return int(json.loads(OFFSET.read_text()).get("offset", 0))
        except Exception:  # noqa: BLE001
            return 0
    return 0


def save_offset(v):
    OFFSET.write_text(json.dumps({"offset": v}))


def append(msg):
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    with INBOX.open("a") as fh:
        fh.write(json.dumps(msg, ensure_ascii=False) + "\n")


def main():
    cfg = load_cfg()
    token, chat_id = cfg["token"], cfg.get("chat_id")
    offset = load_offset()
    backoff = 2
    print(f"tg_inbox: polling as chat_id={chat_id}, starting offset={offset}", flush=True)
    while True:
        try:
            ups = tg("getUpdates", token, offset=offset, timeout=POLL_TIMEOUT,
                     allowed_updates=json.dumps(["message", "edited_message"]))
            backoff = 2
            for u in ups.get("result", []):
                offset = max(offset, int(u.get("update_id", 0)) + 1)
                m = u.get("message") or u.get("edited_message") or {}
                chat = m.get("chat") or {}
                text = (m.get("text") or "").strip()
                if not text:
                    continue
                # only the owner's chat is trusted; anything else is recorded but flagged
                trusted = chat_id is None or chat.get("id") == chat_id
                rec = {"utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "update_id": u.get("update_id"),
                       "from": chat.get("first_name") or chat.get("title") or str(chat.get("id")),
                       "chat_id": chat.get("id"),
                       "trusted": bool(trusted),
                       "text": text,
                       "seen": False}
                append(rec)
                print(f"[in] {rec['utc']} {rec['from']}: {text[:120]}", flush=True)
                if trusted and chat_id:
                    try:
                        tg("sendMessage", token, chat_id=chat_id,
                           text=f"✅ 收到（{rec['utc']}）：{text[:200]}\n"
                                f"已写入 data/tg-inbox.jsonl，我在下一轮会读到。")
                    except Exception as exc:  # noqa: BLE001
                        print(f"  ack failed: {type(exc).__name__}", flush=True)
                low = text.lower()
                if trusted and any(w in low for w in STATUS_WORDS):
                    # answer immediately instead of waiting for the agent to wake up
                    print(f"  -> status query, running push_live.py", flush=True)
                    try:
                        r = subprocess.run([".venv/bin/python", "scripts/push_live.py"],
                                           cwd=ROOT, capture_output=True, text=True,
                                           timeout=600,
                                           env={**os.environ, "PUSH_FORCE": "1"})
                        tail = (r.stdout or r.stderr).strip().splitlines()
                        print(f"  push_live rc={r.returncode}: {tail[-1][:120] if tail else ''}", flush=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"  status push failed: {type(exc).__name__}", flush=True)
                        try:
                            tg("sendMessage", token, chat_id=chat_id,
                               text=f"⚠️ 自动查状态失败：{type(exc).__name__}（已记录，等 agent 处理）")
                        except Exception:  # noqa: BLE001
                            pass
            if ups.get("result"):
                save_offset(offset)
        except urllib.error.HTTPError as exc:
            print(f"tg_inbox HTTPError {exc.code}; backoff {backoff}s", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)
        except Exception as exc:  # noqa: BLE001
            print(f"tg_inbox {type(exc).__name__}: {str(exc)[:120]}; backoff {backoff}s", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)


if __name__ == "__main__":
    main()
