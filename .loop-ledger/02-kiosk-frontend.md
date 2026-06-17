# Artifact: portrait kiosk frontend (v1) — `02-kiosk-frontend`

Branch: `impl/kiosk-frontend` (commit `fdbc4df`, 8 files, +683/-6). Tests: 25 passed
(16 backend preserved + 9 frontend).
Mode: HEADLESS. **Implementer deviation (logged):** codex no-op'd THREE times on this
artifact (two on session `kiosk-frontend-impl`, one fresh `kiosk-frontend-v2`) — each returned
empty with no branch/files; codex was transiently non-functional for this artifact. Per the
no-human-in-the-loop mandate ("make the best call, never stop"), the RELAY orchestrator
(claude) authored the static frontend directly (it is vanilla HTML/CSS/JS + Python tests,
sandbox-testable in-shell). **Cross-vendor integrity preserved:** gemini (gemini-2.5-flash)
performs the independent review; orchestrator casts the grade.

Acceptance contract: vanilla HTML/CSS/JS, no framework/build, DOM-light, animation-free;
renders local cache only; portrait 1080x1920 day/agenda with NOW/NEXT, per-calendar color
stripes, dimmed tentative, in-character staleness chip, first-boot syncing (never blank);
MAX_VISIBLE_ROWS cap; §13 theming isolated in theme.js (system state only) + grep-able
invariant test; BOOYAH audio on 3 system signals only w/ silent fallback; ORIGINAL art only
(real art runtime from git-ignored assets/); static routes added to server.py w/o breaking
the 16 backend tests.

---

## CYCLE 1

### Step 1 — author (claude/relay orchestrator; codex unavailable for this artifact)
Files: `web/index.html` (DOM-light shell), `web/style.css` (portrait 1080x1920, blue/silver
palette, animation-free — no keyframes/animation/transition), `web/app.js` (60s poll of
/api/agenda, home-tz wall-clock read off ISO offset, NOW/NEXT, color stripes, dimmed
tentative, MAX_VISIBLE_ROWS=14, createElement/textContent only, retains last render on fetch
error → never blank, syncing overlay when tier=syncing), `web/theme.js` (§13 surface: consumes
ONLY staleness tier + the 3 system signals; BOOYAH gated on SYSTEM_SIGNALS w/ app-load-once
latch + silent fallback; staleness chip copy; runtime brand-art loader w/ placeholder
fallback). `cyborg_core/server.py` gained static routes (GET / + web/*.js/*.css, content-types,
path-traversal guard) leaving /api/agenda + /health + the 16 backend tests intact.
Tests: `tests/test_static_routes.py` (live-server 200+content-type, api-still-works, traversal
404), `tests/test_frontend_invariant.py` (grep-able §13: forbidden event-content fields absent
from theme.js + no event/agenda indexing; audio gated on system signals; no CDN/framework;
animation-free CSS; MAX_VISIBLE_ROWS + no innerHTML).
- **Sandbox test:** initial run 3 failures — all were the grep invariant catching forbidden
  tokens in my OWN comments (`@keyframes`, `events`, `innerHTML`); reworded comments → re-run
  **25 passed**. (The grep-test working as designed even against the author.)

### Step 2 — review (gemini/gemini-2.5-flash) — DISPATCHED
Sent full frontend source + server static-route semantics + the invariant tests + contract
(no worktree). Asked to hunt: theme.js content-coupling + grep strength; BOOYAH gating/latch/
silent fallback; never-blank guarantee on fetch error/first boot; animation-free + DOM-light;
path-traversal safety; home-tz wall-clock correctness; trademarked-asset leakage.
- (First two gemini dispatches failed: 429 on gemini-3.1-pro, then "Pi process ended without
  response". Re-dispatched on fresh titles w/ model=gemini-2.5-flash + trimmed packet.)
- **gemini cycle-1 verdict: NEEDS-ANOTHER-CYCLE.** 1 BLOCKING: `staleChip(tier, label)` accepts
  a caller-supplied label — a loophole by which app.js *could* thread event content into the
  theming surface; the grep test only scans theme.js internals, not the param origin.

### Step 3 — author response / fix (claude/relay, cycle 2)
ADOPTED the finding (cheap + strengthens the load-bearing §13 invariant). theme.js now OWNS the
label: new signature `staleChip(tier, nowIso, ageSeconds)`, internal `updatedLabel(nowIso,
ageSeconds)` derived from `Date.parse(now) - age*1000` shifted by the ISO offset — no caller
free-text accepted. app.js passes only system state (`data.now`, `staleness.age_seconds`); its
old label helpers deleted. NEW test `test_staleness_label_is_computed_inside_theme_from_system
_time_only` asserts theme.js owns the computation AND the app.js call site passes no event data.
Re-test: **26 passed**. Committed `84e1bbe`.

### Step 4 — grade (gemini cycle-2 confirmation + orchestrator)
**gemini cycle-2 verdict: GO** — "cycle-1 BLOCKING issue fully resolved … label computation
now entirely self-contained within theme.js … no new blocking issues." Orchestrator concurs;
no shared big misses remain. Grade: GO.

### Step 5 — final approval (claude/relay)
Vanilla DOM-light animation-free portrait kiosk; renders local cache only; never-blank on
fetch-error/first-boot; §13 theming structurally isolated (system state only) + grep-enforced;
BOOYAH on 3 system signals w/ silent fallback; no trademarked assets in repo. 26/26 tests.
Zero blocking. **APPROVED.** Merged `impl/kiosk-frontend` → `main`.

deltas_adopted: cycle 2 — moved staleness-label computation into theme.js (system-time only),
deleted app.js label helpers, added call-site §13 invariant test. The cross-model signal: a
parameter's *origin* can breach an isolation invariant even when the module body is clean —
test the call site, not just the module.

