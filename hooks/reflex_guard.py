# -*- coding: utf-8 -*-
"""Reflex guard — SessionStart hook.

Injects LESSONS.md (the always-on reflex layer) and then self-checks the
whole reflex system. Why a guard must check CONTENT and not just size:
byte-budget checks cannot catch silent corruption (control characters from
shell-escaping accidents, dead file references after a move, a domain file
whose trigger header was forgotten). All of these are invisible failures:
the knowledge is still on disk, but it will never load again.

Checks:
  1. LESSONS budget — with headroom: warn at SOFT, fail past HARD. The
     summary line ALWAYS prints current usage, so the trend stays visible.
     (A warning that is always on is the same as no warning.)
  2. Control characters — binary scan of LESSONS + domain files (+ your
     knowledge base, if REFLEX_KB is set).
  3. Dead references — `[see: path]` / `[详见 path]` links that point to
     files that no longer exist.
  4. Trigger reachability — a domain file with no trigger header can never
     fire (silent loss: worse than deletion, because you think it's there).
     Plus a LIVE PROBE of both hooks: a hook that always returns empty
     looks identical, from outside, to "no hit this turn". Probes fire one
     known-hit and one known-miss input each — a degenerate hook that
     answers everything would pass a positive-only probe.

Healthy state prints one summary line; problems get full detail.

Environment:
  REFLEX_HOME    directory holding LESSONS.md and domains/ (default: this
                 script's directory)
  REFLEX_KB      optional path(s) to your markdown knowledge base, separated
                 by os.pathsep; scanned for control chars, used to resolve
                 [see:] references
  REFLEX_BUDGET  hard byte budget for LESSONS.md (default 19000)
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid

HOME = os.environ.get("REFLEX_HOME") or os.path.dirname(os.path.abspath(__file__))
LESSONS = os.path.join(HOME, "LESSONS.md")
DOM = os.path.join(HOME, "domains")
H_DOMAIN = os.path.join(HOME, "reflex_domain.py")
H_ACTION = os.path.join(HOME, "reflex_action.py")
KB_DIRS = [p for p in (os.environ.get("REFLEX_KB") or "").split(os.pathsep) if p]

HARD = int(os.environ.get("REFLEX_BUDGET") or 19000)
SOFT = HARD - 1000
SKIP_DIR = (".git", ".obsidian", "node_modules")
CTRL = bytes(b for b in range(32) if b not in (9, 10, 13))
REF_RE = r"\[(?:see|详见):?\s+([^\]]+)\]"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def kb_md_files():
    for root in KB_DIRS:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if not d.startswith(SKIP_DIR)]
            for f in fn:
                if f.endswith(".md"):
                    yield os.path.join(dp, f)


def resolve(target):
    """Resolve one [see: X] into candidate paths. Unparseable forms return
    nothing — better to miss than to cry wolf: a guard that alarms daily
    is a guard nobody reads (that is what the negative sentinels are for)."""
    out = []
    for raw in re.split(r"[·,，;]", target):
        t = raw.strip().strip("`").strip()
        if not t or t.startswith("<") or t.startswith("http"):
            continue
        if re.match(r"^[A-Za-z]:", t) or t.startswith("/"):
            continue                                   # absolute paths: out of scope
        m = re.match(r"^(.*?\.md)\b", t)               # drop trailing section refs
        if not m:
            continue
        rel = m.group(1).replace("/", os.sep).replace("\\", os.sep)
        for base in [HOME] + KB_DIRS:
            out.append(os.path.join(base, rel))
    return out


def ref_exists(cands):
    return not cands or any(os.path.exists(p) for p in cands)


def probe_hooks():
    """Dry-run both hooks with known inputs, positive and negative."""
    bad = []
    sid = "__reflex_probe_" + uuid.uuid4().hex[:8]
    probe_kw = "__reflex_probe_kw__"
    probe_file = os.path.join(DOM, "__probe__.md")

    def call(script, payload):
        return subprocess.run(
            [sys.executable, script], input=json.dumps(payload),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, env=dict(os.environ, PYTHONIOENCODING="utf-8"))

    try:
        if os.path.exists(H_DOMAIN) and os.path.isdir(DOM):
            io.open(probe_file, "w", encoding="utf-8").write(
                "<!-- triggers: %s -->\nREFLEX_PROBE_BODY\n" % probe_kw)
            try:
                r = call(H_DOMAIN, {"session_id": sid, "cwd": "/nowhere",
                                    "prompt": "probe " + probe_kw})
                if "REFLEX_PROBE_BODY" not in (r.stdout or ""):
                    bad.append("domain hook did not inject on a known hit")
                r = call(H_DOMAIN, {"session_id": sid + "b", "cwd": "/nowhere",
                                    "prompt": "zzz unrelated zzz"})
                if (r.stdout or "").strip():
                    bad.append("domain hook injected on a known miss (negative sentinel)")
            finally:
                try:
                    os.remove(probe_file)
                except Exception:
                    pass
            st = os.path.join(tempfile.gettempdir(), "reflex-state")
            for f in glob.glob(os.path.join(st, "__reflex_probe_*")):
                try:
                    os.remove(f)
                except Exception:
                    pass

        if os.path.exists(H_ACTION):
            src = io.open(H_ACTION, encoding="utf-8").read()
            blk = re.search(r'SELFTEST_BLOCK\s*=\s*"([^"]+)"', src)
            ok = re.search(r'SELFTEST_PASS\s*=\s*"([^"]+)"', src)
            if blk:
                r = call(H_ACTION, {"session_id": sid, "tool_name": "Bash",
                                    "tool_input": {"command": blk.group(1)}})
                if r.returncode != 2:
                    bad.append("action hook failed to block SELFTEST_BLOCK "
                               "(exit %s, expected 2)" % r.returncode)
            if ok:
                r = call(H_ACTION, {"session_id": sid, "tool_name": "Bash",
                                    "tool_input": {"command": ok.group(1)}})
                if r.returncode != 0 or (r.stdout or "").strip():
                    bad.append("action hook reacted to a harmless command "
                               "(negative sentinel)")
    except Exception as e:
        bad.append("probe itself failed %s: %s" % (type(e).__name__, e))
    return bad


def main():
    # -- primary duty: inject the reflex layer; checks must never block it --
    print("=== Always-on reflex layer LESSONS.md (scan before starting work) ===")
    try:
        sys.stdout.write(io.open(LESSONS, encoding="utf-8").read())
    except Exception as e:
        print("!! cannot read LESSONS.md: %s" % e)
        return

    warn = []
    try:
        # 1. budget with headroom
        n = os.path.getsize(LESSONS)
        if n > HARD:
            warn.append("[FAIL] LESSONS over budget: %d / %d bytes. Demote the "
                        "longest domain-specific entries into domains/ before "
                        "this session ends." % (n, HARD))
        elif n >= SOFT:
            warn.append("[WARN] LESSONS has only %d bytes left (%d / %d). "
                        "Before adding a new entry, demote an old one that only "
                        "matters in one domain." % (HARD - n, n, HARD))

        # 2. control characters
        dirty = []
        trig_files = sorted(f for f in glob.glob(os.path.join(DOM, "*.md"))
                            if not os.path.basename(f).startswith("__probe__"))
        for p in [LESSONS] + trig_files + list(kb_md_files()):
            b = io.open(p, "rb").read()
            if any(c in b for c in CTRL):
                dirty.append(os.path.basename(p))
        if dirty:
            warn.append("[FAIL] %d file(s) contain control characters (usually "
                        "shell-escaping accidents, invisible to the eye): %s"
                        % (len(dirty), ", ".join(dirty[:6])))

        # 3. dead references
        dead = []
        txt = io.open(LESSONS, encoding="utf-8").read()
        for m in re.findall(REF_RE, txt):
            if not ref_exists(resolve(m)):
                dead.append("LESSONS -> " + m.strip()[:60])
        for tf in trig_files:
            t = io.open(tf, encoding="utf-8").read()
            for m in re.findall(REF_RE, t):
                if not ref_exists(resolve(m)):
                    dead.append(os.path.basename(tf) + " -> " + m.strip()[:60])
        if dead:
            warn.append("[FAIL] %d dead reference(s) (following them hits "
                        "nothing): %s" % (len(dead), "; ".join(dead[:6])))

        # 4. trigger reachability + live probes
        naked = []
        for tf in trig_files:
            head = io.open(tf, encoding="utf-8").read(1200)
            m = re.search(r"<!--\s*triggers:\s*(.*?)-->", head, re.S)
            c = re.search(r"<!--\s*cwd:\s*(.*?)-->", head, re.S)
            if not ((m and m.group(1).strip()) or (c and c.group(1).strip())):
                naked.append(os.path.basename(tf))
        if naked:
            warn.append("[FAIL] %d domain file(s) have no trigger header — the "
                        "content exists but can NEVER load (silent loss, worse "
                        "than deletion): %s\n   fix: add "
                        "<!-- triggers: word1, word2 --> to the file header"
                        % (len(naked), ", ".join(naked)))
        broken = probe_hooks()
        if broken:
            warn.append("[FAIL] hook probe failed: %s\n   (this class of failure "
                        "is silent: a dead hook looks exactly like 'no hit')"
                        % "; ".join(broken))

        print()
        if warn:
            print("=== !! reflex self-check FAILED ===")
            for w in warn:
                print(w)
        else:
            print("=== OK reflex self-check: LESSONS %d/%d bytes (%d left) | "
                  "%d domain file(s), triggers present, hooks probed alive | "
                  "control chars 0 | dead refs 0 ===" %
                  (n, HARD, HARD - n, len(trig_files)))
    except Exception as e:
        print("\n!! self-check did not finish (%s: %s) — that is the guard's own "
              "problem and does NOT mean the system is healthy."
              % (type(e).__name__, e))


main()
