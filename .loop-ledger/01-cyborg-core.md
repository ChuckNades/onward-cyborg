# Artifact: cyborg-core fetch/cache backend (v1) — `01-cyborg-core`

Branch: `impl/cyborg-core` (commit `0e43629`, 21 files, 1115 insertions).
Mode: HEADLESS — implementer = **codex** (codex-native, gpt-5.5); cross-vendor reviewer =
**gemini** (pi / gemini-2.5-flash); grade cast by **claude/relay** orchestrator. (claude_code
unavailable this run — stalls on UI attach; abandoned and re-implemented via codex.)

Acceptance contract: stdlib `http.server`; deps `icalendar`+`recurring-ical-events` pinned;
all §12 event cases; per-calendar color from config; atomic USB→microSD last-known-good store
(change-gated); staleness tiers + first-boot syncing; `/api/agenda` + `/health`; §13-clean
BOOYAH system-event signaling w/ named rate-limit constant; grep-able §13 invariant test;
injectable clock+fetcher; offline pytest.

---

## CYCLE 1

### Step 1 — author (codex/gpt-5.5)
Built `cyborg_core/` package: `config.py` (TOML, per-calendar color, behavior flags),
`parser.py` (ICS→NormalizedEvent, recurring-ical-events expansion, all §12 cases, `select_next`
+ `event_sort_key`), `store.py` (atomic temp→fsync→os.replace + parent-dir fsync, change-gated
`write_if_changed`, USB-primary/microSD-fallback `StoreStatus`), `staleness.py` (fresh/stale/
on-backup + syncing), `signals.py` (SignalLimiter, named `REFRESH_SIGNAL_RATE_LIMIT=10min`,
imports only datetime — no event fields), `service.py` (CyborgService orchestration, injectable
clock/fetcher/network/undervoltage, `/api/agenda`+`/health` payloads), `server.py` (stdlib
ThreadingHTTPServer handler). Tests: 6 fixtures + 4 test modules, 16 tests. Pinned
`icalendar==6.3.1`, `recurring-ical-events==3.8.0`.
- **Sandbox test:** `16 passed in 0.71s` (codex), independently re-verified by orchestrator
  (`16 passed in 0.62s`).
- Assumption: no vendored wheelhouse this pass (scoped to backend+tests+reqs+config+fixtures;
  wheelhouse deferred to provisioning artifact per design B7/A3).

### Step 2 — review (gemini/gemini-2.5-flash) — DISPATCHED
Sent diff/source + contract only (no worktree). Asked to hunt: §13 structural invariant
coverage (grep scans only signals.py — sufficient?), `next` ordering incl. in-progress
all-day multi-day, atomic durability (file+dir fsync, temp cleanup), change-gate skip/double
-write, DST correctness, USB fallback read-only + /health surfacing, RECURRENCE-ID/EXDATE +
stable id.
- First gemini dispatch FAILED (429: harness picked `gemini-3.1-pro`, free-tier limit 0).
  Re-dispatched with explicit `model: gemini-2.5-flash` → succeeded.
- **gemini verdict: GO.** BLOCKING: none. NON-BLOCKING: none. SUGGESTION: document the
  injectable clock/fetcher injection points + verify the §13 grep regex specificity.

### Step 3 — author response (claude/relay on codex's behalf)
No blocking issues raised → no code changes required. Suggestion is doc-clarity only; the
injection IS via constructor args (`CyborgService.__init__(..., clock=None, fetcher=None)`,
`normalize_calendar(..., now=...)`) and is already unit-tested (FrozenClock + fixture fetcher
in test_http_service.py). Recorded; no delta to source.

### Step 4 — grade (claude/relay orchestrator casts; gemini already graded GO)
Independent adversarial re-audit by orchestrator confirmed: select_next ordering (all-day in
-progress vs timed, in-progress-timed exclusion) correct; atomic durability (file+dir fsync,
temp cleanup) correct; change-gate safe across restart (re-reads current file content);
recurrence + stable id deterministic; USB→microSD fallback surfaced in /health; §13 signals
module structurally content-free. BIG MISSES hunted: none shared. One cross-cutting carry:
the FRONTEND theming surface needs its OWN grep-able §13 test (enforced in artifact-2 contract).
**Grade: GO.**

### Step 5 — final approval (claude/relay, headless approver)
All §12 cases + atomic LKG + staleness + /health + §13 BOOYAH signaling implemented and
sandbox-tested (16/16, independently re-verified). Zero blocking issues. **APPROVED.**
Merged `impl/cyborg-core` → `main`.

deltas_adopted (cycle 1): none to source (clean GO); doc-clarity suggestion noted; frontend
§13-grep carry-forward added to artifact-2 contract.

