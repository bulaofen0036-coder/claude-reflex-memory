# claude-reflex-memory

**Reflex, not recall.** A zero-database, zero-LLM-call, plain-markdown memory
architecture for Claude Code (and any hook-capable coding agent): lessons fire
when their *stimulus* appears — not because you re-read a giant instructions
file every morning.

[中文说明 → README.zh-CN.md](README.zh-CN.md)

## The idea

Most agent-memory projects answer *"how do I store and search everything?"*
(vector DBs, knowledge graphs, LLM extraction pipelines). This project answers
a different question: **when should a lesson load?** It routes every lesson by
its *trigger modality*:

| Layer | What lives there | When it loads | Cost of a miss |
|---|---|---|---|
| `LESSONS.md` | lessons any session could hit (red lines, judgment rules, environment traps) | every session, auto-injected | — (always on, **hard byte budget**) |
| `domains/*.md` | lessons that only matter during deep work in one domain | a trigger keyword appears in the prompt or cwd | zero — no hit, no bytes |
| `reflex_action.py` | red lines only catchable at the moment of execution | the *about-to-run command* matches a regex; inject a reminder or hard-block | zero |
| your knowledge base | full prose, the **single source of truth** | agent follows a `[see: file.md]` link when it needs depth | zero |

Three design rules hold it together:

1. **Single write.** Full prose is written exactly once, in your knowledge
   base (an Obsidian vault works perfectly). Every layer above it holds one-line
   indexes ending in `[see: …]`. Duplicated prose always diverges; an index
   cannot.
2. **Hard budget on the always-on layer.** `LESSONS.md` has a byte budget
   (default 19 000). When it fills up you don't delete lessons — you *demote*
   them to a domain file, where a miss costs nothing. (Letta's memory-block
   budgets converged on the same idea; here it's enforced by the guard, not by
   discipline.)
3. **The guard checks content, not just size.** Byte counters can't catch the
   failures that actually kill file-based memory systems: control characters
   from shell-escaping accidents, dead `[see:]` links after a file moves, a
   domain file whose trigger header was forgotten (the content still exists —
   it just *never loads again*, and nothing tells you). `reflex_guard.py`
   checks all of these on every session start, and **live-probes both hooks**
   with a known-hit and a known-miss input each — because a dead hook that
   returns nothing is indistinguishable from "no match this turn", and a
   degenerate hook that answers everything would pass a positive-only probe.

## What it is not

- No database, no embeddings, no LLM calls, no background daemon. Three Python
  files, stdlib only.
- Not an auto-capture system. *You* (or your agent, following your rules)
  distill lessons; nothing is recorded silently. If you want automatic session
  compression, [claude-mem](https://github.com/thedotmack/claude-mem) is the
  complement, not the competitor.
- Not a note-taking MCP server. If you want your agent to browse a knowledge
  graph, look at [basic-memory](https://github.com/basicmachines-co/basic-memory).
  This project is about *making the right lesson fire at the right moment*.

## Quickstart

```bash
# 1. deploy
mkdir -p ~/.claude/reflex
cp hooks/*.py            ~/.claude/reflex/
cp templates/LESSONS.md  ~/.claude/reflex/
cp -r templates/domains  ~/.claude/reflex/domains

# 2. wire the hooks
#    merge templates/settings.hooks.json into ~/.claude/settings.json,
#    replacing <REFLEX> with your deploy path

# 3. (optional) point the guard at your knowledge base
#    export REFLEX_KB=/path/to/your/obsidian-vault

# 4. verify
python ~/.claude/reflex/reflex_guard.py
# expect: "=== OK reflex self-check: ... hooks probed alive ... ==="
```

Then start a Claude Code session: `LESSONS.md` is injected with a one-line
health summary. Say a word that matches a domain file's trigger header and
that file's lessons appear — once per session, silently otherwise.

## Writing lessons

One lesson, one line: `trigger → one-sentence correct move [see: file.md]`.

- **Where it goes** is decided by what triggers it (table above), not by topic.
- New domain file → **must** add `<!-- triggers: word1, word2 -->` to its
  header. Include synonyms and aliases (users say "portal", "the UI", "TIA"
  for the same thing). The guard fails loudly if the header is missing.
- When a conclusion is overturned, **mark it invalid, don't delete it**:
  append `> ⚠️ superseded (date): replaced by X, see …`. The history of a
  pitfall is an asset (Graphiti's bi-temporal edges, done with one line of
  markdown).
- Action red lines go in `reflex_action.py` as INJECT (remind) or BLOCK
  (exit 2 with a reason). Every BLOCK must leave an explicit key
  (`PUSH_OK=1` prefix) — a rule with no override becomes a wall, and walls
  get demolished.

## Why regex-triggered files instead of retrieval?

Because a working set of distilled lessons is small (tens of KB), and what
kills you is not *finding* a lesson when you search — it's the lesson **not
firing when you didn't think to search**. Reflexes are stimulus-driven.
Keyword triggers on the prompt, regex triggers on the command line, and an
always-on core get you that; a vector index does not (nothing queries it at
the moment you're about to `git push --force`).

The trade-off is honest: this scales to *distilled lessons*, not to raw
archives. Keep the archive in your knowledge base and link to it.

## Failure modes, and what covers them

| Failure | Covered by |
|---|---|
| always-on layer bloats, attention dilutes | hard budget + demotion warning |
| prose duplicated, copies diverge | single-write rule (`[see:]` links) |
| file corrupted by shell-escaping accident | control-character scan |
| knowledge base file moved, links dead | dead-reference check |
| domain file forgot its trigger header | reachability check (loud fail) |
| hook silently dead (returns nothing forever) | live probe, positive + negative |
| guard itself degrades into noise | negative sentinels; unparseable refs are skipped, not reported (a guard that cries wolf daily is no guard) |

## Provenance

Extracted from a system that has been the daily driver of an industrial-
automation engineer (Siemens PLC / TIA Portal work) since mid-2026: ~200 MB
Obsidian knowledge base as the single source of truth, a budgeted LESSONS
layer, a dozen domain files, and action red lines that have each earned their
place by being violated at least once before becoming a reflex. The scripts
here are cleaned-up, path-independent rewrites of that production setup.

## License

MIT
