#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sticker Commenter — auto-post a sticker from a chosen sticker pack
as a comment under every new channel post.

How it works (Telegram mechanics):
  * A channel has a linked discussion group.
  * Every channel post is auto-forwarded into that group as a message
    with `is_automatic_forward=True` and `forward_origin.type="channel"`.
  * A bot that is a member/admin of the group receives that message via
    getUpdates and replies to it with sendSticker — the reply shows up
    as a comment under the original channel post.

Config: copy `.env.example` to `.env` and fill it in.

Demo (live): https://t.me/stickerdemo_k1 — every post in the channel
gets a sticker comment automatically.
"""
import io
import json
import os
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        ".env")


def _env(key, default=None):
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, default)


TOKEN = _env("TG_BOT_TOKEN")
if not TOKEN:
    sys.exit("TG_BOT_TOKEN is not set (.env or environment)")

CHANNEL_ID = int(_env("CHANNEL_ID", "0"))
GROUP_ID = int(_env("GROUP_ID", "0"))
STICKER_SET = _env("STICKER_SET", "HotCherry")
STICKER_INDEX = int(_env("STICKER_INDEX", "0"))
DELAY_SEC = float(_env("DELAY_SEC", "0"))

API = f"https://api.telegram.org/bot{TOKEN}"


def call(method, **kw):
    """Bot API call with retries (api.telegram.org can be laggy)."""
    for attempt in range(4):
        try:
            r = requests.post(f"{API}/{method}", data=kw, timeout=60)
            j = r.json()
            if not j.get("ok"):
                raise RuntimeError(f"{method} failed: {j}")
            return j["result"]
        except requests.RequestException as e:
            if attempt == 3:
                raise
            print(f"  retry {attempt + 1} after {type(e).__name__}",
                  flush=True)
            time.sleep(3)


def get_pack_sticker():
    """file_id of the sticker inside the configured pack."""
    s = call("getStickerSet", name=STICKER_SET)
    st = s["stickers"][STICKER_INDEX % len(s["stickers"])]
    return st["file_id"], st.get("emoji"), s["name"]


def send_sticker_comment(group_msg_id, file_id):
    return call("sendSticker", chat_id=GROUP_ID, sticker=file_id,
                reply_parameters=json.dumps(
                    {"message_id": group_msg_id}))


def main():
    file_id, emoji, pack = get_pack_sticker()
    print(f"sticker-commenter running | pack={pack} "
          f"idx={STICKER_INDEX} emoji={emoji} delay={DELAY_SEC}s",
          flush=True)
    offset, seen = 0, set()
    while True:
        try:
            updates = call("getUpdates", offset=offset, timeout=30,
                           allowed_updates=json.dumps(["message"]))
        except Exception as e:
            print("poll error:", e, flush=True)
            time.sleep(5)
            continue
        for u in updates:
            offset = max(offset, u["update_id"] + 1)
            m = u.get("message")
            if not m or not m.get("is_automatic_forward"):
                continue
            fchat = (m.get("forward_origin") or {}).get("chat", {}) \
                or m.get("forward_from_chat", {})
            if m["chat"]["id"] != GROUP_ID \
                    or fchat.get("id") != CHANNEL_ID:
                continue
            if m["message_id"] in seen:
                continue
            seen.add(m["message_id"])
            src = m.get("forward_from_message_id") or \
                (m.get("forward_origin") or {}).get("message_id")
            print(f"new post #{src} -> group msg {m['message_id']}; "
                  f"waiting {DELAY_SEC}s", flush=True)
            time.sleep(DELAY_SEC)
            res = send_sticker_comment(m["message_id"], file_id)
            print(f"  sticker comment sent: msg {res['message_id']}",
                  flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
