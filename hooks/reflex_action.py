# -*- coding: utf-8 -*-
"""Reflex action layer — PreToolUse hook (matcher: Bash|PowerShell).

Regex-matches the literal command that is ABOUT to run. Two rule classes:

  INJECT — inject a reminder, let the command run (once per session per
           rule: it is already in context after the first time, repeating
           it only wastes tokens).
  BLOCK  — exit code 2: actually stop this call and feed the reason back
           to the model. Every BLOCK rule MUST leave an explicit key,
           otherwise the action becomes permanently impossible. The key
           here: prefix the command with `PUSH_OK=1` — a deliberate act.

Why this layer exists at all: rules that live only in an instructions file
get read once and violated anyway. A reflex fires when the stimulus
appears — at the exact moment of action — not during a morning read-through.

Failures are silently permissive (a broken hook must not block normal
work) — EXCEPT for BLOCK rules: if the pattern matched, we must block.
Better a false block than a leaked push.

Edit the rule lists below to fit your own red lines. If you change them,
also update SELFTEST_* so the guard keeps probing something real.
"""
import io
import json
import os
import re
import sys
import tempfile

STATE = os.path.join(tempfile.gettempdir(), "reflex-state")
APPROVE_TOKEN = "PUSH_OK=1"

# Used by reflex_guard.py to probe this hook end-to-end.
# SELFTEST_BLOCK must be blocked (exit 2); SELFTEST_PASS must pass silently.
SELFTEST_BLOCK = "git push --force origin main"
SELFTEST_PASS = "echo reflex-selftest"

# (id, regex, reminder)
INJECT = [
    ("kill",
     r"Stop-Process|taskkill|\bpkill\b|\bkill\s+-\d",
     "[reflex:kill] Before killing: print the FULL command line of every "
     "candidate and confirm one by one; match by full path, never by a "
     "filename fragment; exclude your own PID. A process whose parent is "
     "alive is not an orphan."),
    ("destroy",
     r"rm\s+-rf|rm\s+-fr|Remove-Item[^|\n]*-Recurse|\bdel\s+/[sq]",
     "[reflex:destroy] Look at the target's CURRENT state before deleting. "
     "Never trust memory or docs about what is on disk — check the disk."),
]

BLOCK = [
    ("force-push",
     r"\bgit\s+push\b[^|\n]*(--force|-f\b)|\bgh\s+repo\s+delete\b",
     "[redline] Force-push / repo delete intercepted. Rewriting published "
     "history or deleting a repo is irreversible for collaborators. If the "
     "user explicitly approved it, re-run the command with " + APPROVE_TOKEN +
     " prefixed."),
]


def load_state(sid):
    try:
        return set(json.load(io.open(os.path.join(STATE, sid + ".act.json"),
                                     encoding="utf-8")))
    except Exception:
        return set()


def save_state(sid, done):
    try:
        os.makedirs(STATE, exist_ok=True)
        json.dump(sorted(done),
                  io.open(os.path.join(STATE, sid + ".act.json"), "w",
                          encoding="utf-8"))
    except Exception:
        pass


def main():
    data = json.loads(sys.stdin.read() or "{}")
    cmd = str((data.get("tool_input") or {}).get("command") or "")
    if not cmd:
        return
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id") or "nosid"))

    # -- BLOCK first: if matched, block every time (no dedup) --
    if APPROVE_TOKEN not in cmd:
        for _key, pat, msg in BLOCK:
            if re.search(pat, cmd, re.I):
                sys.stderr.write(msg)
                sys.exit(2)

    # -- INJECT: remind once per session per rule --
    done = load_state(sid)
    hits, fresh = [], []
    for key, pat, msg in INJECT:
        if key in done:
            continue
        if re.search(pat, cmd, re.I):
            hits.append(msg)
            fresh.append(key)

    if not hits:
        return                        # no hit: zero injection

    done.update(fresh)
    save_state(sid, done)
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n".join(hits),
        }
    }, ensure_ascii=False))


try:
    main()
except SystemExit:
    raise                             # BLOCK's exit code 2 must propagate
except Exception:
    pass                              # anything else: silently permissive
sys.exit(0)
