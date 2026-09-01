# -*- coding: utf-8 -*-
"""Reflex domain layer — UserPromptSubmit hook.

Injects a domain knowledge file into context ONLY when the current prompt
(or cwd) hits one of the trigger keywords declared in that file's header.
No hit -> not a single byte injected.

Each file is injected AT MOST ONCE PER SESSION. Without this dedup, a long
session in one domain would re-inject the same content on every message —
worse than keeping it resident. This is the easiest part to get wrong.

Trigger keywords live in the file header itself:
    <!-- triggers: keyword1, keyword2, ... -->
    <!-- cwd: /path/fragment -->          (optional, matches working dir)
Keeping triggers next to the content (instead of a separate index) prevents
the two from drifting apart.

Any failure exits 0 silently: a broken hook must never block the user's
conversation. The guard (reflex_guard.py) actively probes this script,
because a hook that silently returns nothing looks identical to "no hit".
"""
import glob
import io
import json
import os
import re
import sys
import tempfile
import time

HOME = os.environ.get("REFLEX_HOME") or os.path.dirname(os.path.abspath(__file__))
DOM = os.path.join(HOME, "domains")
STATE = os.path.join(tempfile.gettempdir(), "reflex-state")


def load_meta(path):
    """Read trigger keywords from the file header. Unreadable/absent header
    means the file can never fire — the guard reports that as an error
    (silent loss is the one new failure mode of this design)."""
    head = io.open(path, encoding="utf-8").read(1200)
    kws, cwds = [], []
    m = re.search(r"<!--\s*triggers:\s*(.*?)-->", head, re.S)
    if m:
        kws = [x.strip().lower() for x in m.group(1).split(",") if x.strip()]
    m = re.search(r"<!--\s*cwd:\s*(.*?)-->", head, re.S)
    if m:
        cwds = [x.strip().lower() for x in m.group(1).split(",") if x.strip()]
    return kws, cwds


def body_of(path):
    """Strip header comments; inject the body only."""
    txt = io.open(path, encoding="utf-8").read()
    return re.sub(r"^\s*(<!--.*?-->\s*)+", "", txt, flags=re.S).strip()


def sweep_state():
    """Drop per-session state files older than 7 days."""
    try:
        cutoff = time.time() - 7 * 86400
        for f in glob.glob(os.path.join(STATE, "*.json")):
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
    except Exception:
        pass


def main():
    data = json.loads(sys.stdin.read() or "{}")
    prompt = str(data.get("prompt") or "").lower()
    cwd = str(data.get("cwd") or "").lower()
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id") or "nosid"))

    if not os.path.isdir(DOM):
        return

    os.makedirs(STATE, exist_ok=True)
    sweep_state()
    spath = os.path.join(STATE, sid + ".json")
    try:
        done = set(json.load(io.open(spath, encoding="utf-8")))
    except Exception:
        done = set()

    chunks, fresh = [], []
    for path in sorted(glob.glob(os.path.join(DOM, "*.md"))):
        key = os.path.basename(path)
        if key in done:
            continue
        kws, cwds = load_meta(path)
        hit = any(k in prompt for k in kws) or any(c in cwd for c in cwds)
        if not hit:
            continue
        chunks.append(body_of(path))
        fresh.append(key)

    if not chunks:
        return                       # no hit: zero injection

    done.update(fresh)
    try:
        json.dump(sorted(done), io.open(spath, "w", encoding="utf-8"))
    except Exception:
        pass                         # losing state only causes re-injection;
                                     # it must not block the conversation

    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext":
                "=== Domain reflex layer (matched this turn; injected once per session) ===\n"
                + "\n\n".join(chunks),
        }
    }, ensure_ascii=False))


try:
    main()
except Exception:
    pass                             # a broken hook must never break the chat
sys.exit(0)
