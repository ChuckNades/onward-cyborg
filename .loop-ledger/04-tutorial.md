# Artifact: v1 + v2 build TUTORIAL — `04-tutorial`

Branch: `impl/tutorial` (commit `be73fab`). Files: `docs/tutorial/index.html` (863 lines,
self-contained offline web), `docs/tutorial/README.md`; plus a 1-line kiosk autoplay fix to
`deploy/openbox/autostart` so BOOYAH can fire without a click.
Mode: HEADLESS. **Author = claude/relay orchestrator** (per relay rules the lead writes prose/
docs itself — not delegated to codex). Cross-vendor reviewer = **gemini/gemini-2.5-flash**;
grade by orchestrator.

Contract: infallible for a total novice (exact commands + "you'll know it worked" + inline "if
it didn't" per step, no gaps/forward-refs), FUN (missions/roles/badges/certificate/Cyborg
voice), offline-usable + print/PDF, BOTH v1 and v2, embeds wiring diagrams, references ONLY
sandbox-tested code.

---

## CYCLE 1

### Step 1 — author (claude/relay)
Wrote the offline self-contained tutorial: hero + how-to + crew roles + badges; pre-flight (BOM,
tools, Apple ICS link how-to, Golden Safety Rules + ASCII 40-pin header map). Weekend 1 (v1) = 9
missions (flash/boot, fan, DS3231 RTC, install code+calendar, USB cache, portrait kiosk+
autostart, BOOYAH audio, wall mount w/ fridge caution, BONUS power button + screen schedule),
each with exact commands, a green "✅ you'll know it worked", and a "🛟 if it didn't" recovery;
/health table; v1 acceptance checklist + certificate. Weekend 2 (v2) = clearly-labeled
"next-level BLUEPRINT" (zoned hub: weather Open-Meteo no-key, touch chores+meals local JSON on
USB, swipe weeks) mapped to the exact v1 backend/frontend seams, honoring §13 + Pi-3B budget;
v2 acceptance + cert. Reference: Troubleshooting HQ, command cheat-sheet, badge checklist.
Interactive JS (localStorage checkbox progress, print button); print CSS expands troubleshooting.
- Made one correctness fix while authoring: the kiosk needs `--autoplay-policy=no-user-gesture-
  required` for BOOYAH audio to auto-play; added it to `deploy/openbox/autostart` (the only code
  touched). All 33 backend/frontend/provisioning tests still pass; tutorial verified offline
  (no external resource loads) and HTML well-formed.

### Step 2 — review (gemini/gemini-2.5-flash) — DISPATCHED
Sent the full structure + the authoritative code facts (ports/paths/services/config keys) and
asked it to hunt: wrong/mis-ordered/incompletable commands, any path/port/service/config mismatch
vs the shipped code, missing "worked/if-it-didn't" per step, any presentation of v2 (unbuilt) as
done, §13/perf contradictions, safety completeness, and whether audio autoplay is truly enabled.
- gemini returned EMPTY 3× on the tutorial packet (transient pi/flash worker failure). To preserve
  genuine cross-vendor review, the orchestrator (a) ran an objective consistency audit grepping the
  tutorial against the shipped code (port 8765, /health, config keys, cyborg-fetch, LABEL=CYBORG,
  mkfs.ext4 -L, getty autologin, autoplay flag @ autostart:20, 9 missions / 15 worked-checks /
  23 recovery boxes, v2 labeled BLUEPRINT 4×, safety rules present) and (b) dispatched **codex** as
  the independent cross-vendor reviewer (a different vendor than the author).

### Step 2b — review (codex, cross-vendor) — cycle 1
**FAILS CONTRACT — 6 BLOCKING:** (1) M4 `python3 -m venv` runs before `python3-venv` installed;
(2) M4 success claims events render before a writable cache exists (backend serves from cache only) —
false until M5/M6; (3) `git clone <placeholder>` not literal; (4) BOOYAH `cp ~/my-booyah.mp3` references
a non-existent file + no shipped asset; (5) README claims print expands troubleshooting but CSS doesn't
force closed <details> open; (6) "every step" promise vs steps lacking per-step recovery (M5/M8). Plus
non-blocking (/health "green-ish", do_audio on Bookworm, stray </p>, v2 cert).

### Step 3 — author fix (claude/relay) — cycle 2
ADOPTED all 6: M1 installs `git python3-venv python3-pip`; M4 success verifies `/health fetch.ok:true`
and states 'syncing' is expected until M5 (M5 = 'events appear'); concrete `cp -r`/`scp`/`git clone`
options + `ls cyborg_core` check; M7 generates a real `booyah.mp3` on-device with `sox` (+ `arecord`
option), repo ships no audio; `beforeprint`/`afterprint` JS force-opens all <details>; softened how-to
promise + added M5 recovery; removed stray </p>, reworded /health to raw JSON, Bookworm audio note,
'v2 files don't exist yet' callout. 33 tests pass; HTML balanced; offline.

### Step 4 — review (codex) — cycle 2 confirmation
**5/6 resolved; 1 residual BLOCKING:** M5 ran the server in background then `kill %1` BEFORE the success
box said to open the calendar — URL dead at check time.

### Step 5 — author fix (claude/relay) — cycle 3
M5 step 4 now: run in background, ls the cache file, **leave it running**, open the calendar URL +
confirm events, THEN `kill %1`. 33 tests pass; HTML balanced; offline. Commit `bc96ed3`.

### Step 6 — grade + final approval (claude/relay; 3-cycle cap)
The lone residual was a clear, objectively-correct ordering fix, verified by inspection. All 6 codex
blockers resolved. Tutorial is consistent with the shipped+tested code, infallible (exact commands +
worked-checks + recovery), fun (missions/roles/badges/2 certs/BOOYAH), offline + print/PDF, covers v1
(complete) + v2 (labeled blueprint). **Grade: GO. APPROVED.** Merged `impl/tutorial` -> `main`.

deltas_adopted: cycle 2 — venv ordering, cache/events-after-M5 truth, concrete copy commands,
sox BOOYAH, print-opens-details, per-step recovery; cycle 3 — server stays up through the M5 check.
Cross-model signal: a doc reviewer (codex) reading BOTH prose AND code caught runtime command-order
bugs a prose-only or code-only pass misses — review the doc against the system it drives, end-to-end.
