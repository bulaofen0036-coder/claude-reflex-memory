# LESSONS — always-on reflex layer (auto-injected every session)

**Only entries that ANY session could hit belong here.** One lesson = one
line: `trigger → one-sentence correct move`, ending with a `see:` link
pointing at the full write-up in your knowledge base. Full prose lives in
the knowledge base (the single source of truth); this file is an index of
reflexes, never a second copy.

Where a new entry goes depends on WHAT TRIGGERS IT:
- could bite in any session            → this file (hard budget: 19000 bytes)
- only bites during deep work in one domain → `domains/<domain>.md`
  (no size cap — a miss costs nothing; MUST add trigger words to its header)
- only catchable at the moment of execution → a rule in `reflex_action.py`

## Red lines (irreversible / external)
- Before pushing anything to a public repo → check what is private vs
  public every single time; never trust memory about which repo is public.
  [see: <your-kb>/workflow-pitfalls.md]
- Before killing a process → print its full command line and confirm;
  match by full path, never by filename fragment.
- Before deleting / overwriting / moving → look at the target's current
  state first. Memory and docs are not the disk.

## Judgment & verification (cross-domain)
- A tool reporting "success" is not verification — ask what subset it
  actually checked. The criterion must be independent of the thing under
  test. [see: <your-kb>/verification-pitfalls.md]
- Any check/scan/audit harness needs a must-fail sentinel case; if the
  sentinel passes, the harness itself is broken.
- Distinguish "ran and found nothing" from "did not finish running" in
  every report; a swallowed exception disguises a crash as a pass.

## Environment & encoding (daily traps)
- (add your own shell / locale / path traps here)
