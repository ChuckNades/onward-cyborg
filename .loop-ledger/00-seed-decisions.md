# Artifact: Seed Decision Record (DESIGN PASS) — `00-seed-decisions`

Status: **DRAFT (cycle 1, step 1 — Claude/RELAY authored)**
Author: RELAY (Claude orchestrator)
Inputs: `cyborg-tutorial-goal.md` (authoritative; overrides PRD on hardware + v2 scope) + `cyborg-prd.md` v2.1.
Contract: This record must (a) reconcile every conflict between the GOAL brief and the PRD with the brief winning; (b) state an explicit assumption for every gap the brief leaves open; (c) be buildable by a total novice + kids over two weekends on the named hardware; (d) respect the Pi 3B perf ceiling and the §13 theming invariant; (e) never require a human decision mid-build.

---

## A. Conflicts: GOAL brief vs PRD — brief wins (resolved)

| # | Topic | PRD v2.1 said | GOAL brief says (WINS) | Locked decision |
| :- | :- | :- | :- | :- |
| C1 | Compute | Pi **3B+** | Pi **3B** (1 GB, quad-A53) | **Pi 3B.** Tighter ceiling than 3B+ (no Wi-Fi 5/GbE, slower SoC). Build MUST honor R1 even harder. Tutorial written for 3B; notes "3B+ or Pi 4 = bonus headroom, same steps." |
| C2 | Display | 24″ HDMI touch, **landscape** 1920×1080 | Acer **UT222Q 21.5″** touch, **PORTRAIT** 1080×1920, VESA 100×100 | **Portrait 1080×1920.** All layout px, rotation config, and 10-ft legibility pinned to portrait. |
| C3 | Scope | v1 calendar only | **v1 AND v2** (household hub) in the tutorial | Tutorial ships both paths: v1 = Weekend 1, v2 = Weekend 2 ("next level"). |
| C4 | Cache store | "last-known-good store on the Pi" | Same, but **offloaded to Pete's USB stick** to spare the SD card | Cache + last-known-good + theme assets live on USB; boot OS on A1/A2 microSD. |
| C5 | Audio | speaker (3.5 mm / USB) | same + explicit "BOOYAH" | Powered USB or 3.5 mm speaker; §13-bound, rate-limited. |
| C6 | Deliverable | build-ready code brief | **infallible+fun WEB tutorial** (offline, print/PDF), kid missions | Self-contained offline web tutorial + tested files + wiring diagrams. |

## B. Hardware BOM — SEED decisions validated + my gap-fill assumptions

Core (v1 + v2):
1. **Raspberry Pi 3B** (Pete's). [C1]
2. **Acer UT222Q 21.5″ touch**, portrait via VESA 100×100. [C2]
3. **microSD 32 GB A1/A2** (boot OS). Brief recommends 32 GB. → **ASSUME SanDisk/Samsung A1 32 GB**; tutorial gives a "known-good card" sidebar.
4. **USB memory stick** (Pete's) — cache/LKG + git-ignored `assets/`. → **ASSUME ≥8 GB USB 2.0**; formatted ext4 (Linux-native, survives power loss better than FAT for our use; teachable). [C4]
5. **Heatsink set + 5 V fan** — open-air active cooling (ample room behind wall). → **ASSUME GPIO-powered 5 V 30 mm fan on pins 4(5V)+6(GND)**; aluminium heatsink trio. Caution callout on fan finger-guard for kids.
6. **Powered speaker** — USB or 3.5 mm. → **ASSUME 3.5 mm powered mini-speaker** (3B has a 3.5 mm jack; simplest, no USB power contention). [C5]
7. **Official 5 V/2.5 A Pi PSU** + monitor's own adapter on a **switched power strip**.
8. **VESA wall mount, portrait, no frame/box**; Pi to monitor back or cabinet wall via standoffs/Velcro; tidy cable run.

Recommended add-ons — loop decides core vs bonus:
- **DS3231 RTC** → **CORE for reliability, taught as a "Level-Up" mission** (offline-correct time before NTP; the Pi 3B has no RTC and the wall device is often offline-first-boot). I2C on pins 1/3/5/9.
- **Safe-shutdown / power button** → **BONUS mission** (GPIO3 + a tiny script). Real teaching value, not required for a working device.
- **Scheduled screen dim/off hours** → **CORE** (software-only, protects LCD, saves power; `vcgencmd`/wlr-randr or HDMI-CEC + cron).

Proposed additions (route through relay, add to BOM w/ "why"):
- **Cable-management kit** (adhesive clips + sleeve) — "why: portrait wall run stays tidy + safe for kids; cheap." → ADD.
- **Right-angle micro-USB power cable + right-angle HDMI** — "why: reduces depth/strain behind a wall-mounted portrait panel." → ADD (cheap, fixes a real mounting pain).
- **Labeled standoff/Velcro patch** for the Pi — "why: kid 'Master of the Mount' job, repeatable." → ADD.

⚠️ **Safety callout (load-bearing):** cabinet wall has a **fridge on the opposite side** — every screw depth must be checked first. Big caution block in the mounting mission.

## C. Software architecture (honors PRD §7 + §15 R1) — locked

```
Per-calendar secret iCloud ICS URLs ──> fetch/cache service (Python, on Pi)
   polls every 5 min · parses ICS · normalizes to event model (§12)
   writes last-known-good JSON to USB ──> serves localhost ──> Chromium kiosk (portrait)
                                                                renders cached local data only
```

- **Language/stack (gap → ASSUME):** **Python 3 (stdlib http.server + a tiny fetch/parse service)** for the service; **vanilla HTML/CSS/JS** kiosk (NO framework, NO build step) to respect the 3B ceiling (DOM-light, animation-free per §13/§10.6). ICS parsing: **`icalendar` + `recurring-ical-events`** (recurrence/RRULE + TZ correctness is too risky to hand-roll for a novice-facing infallible doc). Justify the two pip deps in the ledger.
- **Process model:** two **systemd** units — `cyborg-fetch.service` (the poller) and `cyborg-kiosk` via autostart — so the browser only ever paints local cached data. Auto-restart (Restart=always) → §6 ~30 s crash recovery.
- **Kiosk:** Chromium in kiosk mode, GPU-heavy effects disabled, portrait rotation set in the display/compositor config.
- **OS (gap → ASSUME):** **Raspberry Pi OS (Bookworm) Lite 32-bit** + minimal X/Openbox OR labwc; 32-bit for 1 GB RAM. Tutorial uses Raspberry Pi Imager.
- **Updates:** git-pull-on-cron from `onward-cyborg`. Config/secrets in `config.local.*` (git-ignored), ICS URLs are config not code (R3).

## D. §13 theming invariant + §12 event contract — carried verbatim into build

- Theming layer may NOT read/branch on event content. BOOYAH fires only on {app load, successful refresh, fetch-failure→recovery}, rate-limited ≤1 / refresh cycle / ~10 min. Provide a **grep-able invariant test** in the test harness.
- Event renderer handles explicitly: all-day, multi-day spanning, overlapping, recurring (RRULE expand), declined/tentative (→ **ASSUME: show tentative dimmed; hide declined**), timezones (render home TZ, DST-safe). "Next" = next start ≥ now in home TZ, all-day ordered ahead of timed for the current day.

## E. v2 zoned layout (portrait) — seed validated/refined

- **Top:** weather + meal-of-the-day.
- **Middle (anchor):** calendar/agenda (the v1 surface, unchanged).
- **Bottom:** chore chart (touch check-off) + meal-prep/week's meals.
- Touch interactions: check off chores, swipe weeks. Still honors §13 (no theming branch on event content).
- **ASSUME v2 data sources:** chores + meals from a **local editable JSON on USB** (no cloud, no write-back to calendar → constitution-clean); weather from a **single free no-key endpoint** (e.g. Open-Meteo, no API key — fits "no API keys"). Route weather choice through implementation relay.

## F. Tutorial format — locked

Self-contained offline web tutorial (Cyborg-themed, interactive step checkboxes, embedded SVG/mermaid diagrams, collapsible troubleshooting, kid-mission framing) + clean print/PDF export. Structure: **missions/levels** w/ checkpoints, difficulty stars, time estimates, kid roles (Captain of Cables, Commander of Code, Master of the Mount), "✅ You'll know it worked when…", "🛟 If it didn't…", badge/sticker checklist, final BOOYAH certificate. Wiring diagrams required (SVG/mermaid), photo-slot markers.

## G. Open assumptions registry (all resolved in-loop, no human asked)

| ID | Gap | Assumption made | Risk if wrong |
| :- | :- | :- | :- |
| A1 | OS image | Pi OS Bookworm **Lite 32-bit** + minimal compositor | Medium — desktop image heavier on 1 GB |
| A2 | USB filesystem | ext4 | Low — could use exFAT if cross-mount needed |
| A3 | ICS libs | `icalendar` + `recurring-ical-events` | Low — vetted, but adds 2 deps |
| A4 | Speaker | 3.5 mm powered | Low |
| A5 | Fan power | 5 V GPIO, always-on | Low — could add transistor control as bonus |
| A6 | RTC | DS3231 as CORE level-up | Low |
| A7 | declined/tentative | tentative dim, declined hidden | Low — easily flipped in config |
| A8 | v2 weather | Open-Meteo (no key) | Low |
| A9 | v2 chores/meals store | local JSON on USB | Low |

---

### Acceptance contract for this design artifact (what Codex must check)
1. Every brief↔PRD conflict resolved with the brief winning, and none missed.
2. Every gap has a stated assumption + fallback.
3. Hardware set is internally consistent (power, pins, cooling, mount) and novice-safe.
4. Architecture respects the Pi **3B** ceiling and §13/§12.
5. Nothing requires a human decision mid-build.
6. v1 and v2 are both covered.

---

# CYCLE 1 — Claude/RELAY response to Codex review (step 3)

Codex returned 8 BLOCKING, 4 NON-BLOCKING, 3 SUGGESTION. **Adopted 14 of 15** (one clarification on B7). Resolutions below are now binding decisions that supersede the draft above where they conflict.

## Blocking — resolutions

**B1 — GPIO pin conflict (DS3231 SCL=GPIO3 vs shutdown button GPIO3). ADOPTED.**
- DS3231 RTC owns I2C: **SDA=GPIO2 (pin 3), SCL=GPIO3 (pin 5), 3V3=pin 1, GND=pin 9.**
- Safe-shutdown button moves to **GPIO17 (physical pin 11)** + GND (pin 14), soft-shutdown via a tiny systemd-run script (not the GPIO3 wake-from-halt trick).
- Note in tutorial: the GPIO3 "short-to-wake-a-halted-Pi" feature is **mutually exclusive** with the DS3231 (both use GPIO3); since RTC is CORE, we do **not** use GPIO3 wake. Documented in the wiring table (§H).

**B2 — "Openbox or labwc" = human decision. ADOPTED.** Single locked stack:
**Raspberry Pi OS Bookworm Lite 32-bit + Xorg + Openbox + unclutter + Chromium (kiosk).** Chosen over Wayland/labwc because Xorg+Openbox is the most-documented, lightest, novice-reproducible path on a 1 GB Pi 3B, and gives us simple, well-understood portrait rotation (`xrandr`) + touch mapping (`xinput`). labwc/Wayland only appears in an appendix **if** separately tested. Exact package list + config files specified at implementation. Updates A1.

**B3 — Pi 3B performance not designed to the ceiling. ADOPTED** — new **§I Pi 3B Performance Contract** added below (memory budget, gpu_mem, Chromium flags, no compositor, DOM cap, fallbacks).

**B4 — Portrait touch under-specified. ADOPTED.** v1 rotates display **and** applies the touch coordinate-transform matrix so stray/edge touches map correctly even though v1 has no touch interactions (PRD §4 day/agenda only). Method (Xorg): `xrandr --output <HDMI> --rotate left` (or right; pick the one matching the physical mount) + `xinput set-prop "<touch device>" "Coordinate Transformation Matrix" <90° matrix>`, persisted via an Xorg config snippet + a calibration "touch the four corners" verification mission. Fallback: mouse/keyboard operation for v1. Touch *interactions* (check chores, swipe weeks) are v2. Updates §E.

**B5 — USB ext4 power-loss resilience. ADOPTED in full.**
- Mount **by UUID** in `/etc/fstab` with `nofail,noatime` (kiosk still boots if USB absent).
- All cache/LKG writes are **atomic: write temp file → `fsync` → `os.replace()`** (rename) onto the final path. No in-place rewrites.
- **Bounded write frequency:** LKG written only when fetched data changes, at most once per 5-min cycle.
- **Startup validation:** service checks USB mount + writability; if USB missing/corrupt, **falls back to a read-only bundled sample/LKG on the microSD** and surfaces a status chip (never blanks). Directory ownership set for the service user.
- Keep ext4 (Linux-native, journaled). FAT32 only mentioned as a note if a novice must edit JSON from Windows — but our config editing is done on the Pi, so ext4 stands. Updates A2.

**B6 — Power/fan wiring novice-safety. ADOPTED.**
- Reworded: fan runs off the **5 V header rail (pin 4) + GND (pin 6)** — this is a power rail, **not** a GPIO-switched output (always-on). Require a **known low-current 5 V 30 mm fan (≤0.1 A) with finger guard**, pre-crimped Dupont connector, strain relief, explicit orientation (airflow-over-SoC) diagram, and a bold **"never bridge 5 V to 3.3 V or GND"** warning.
- Right-angle micro-USB power: must be a **tested short adapter rated ≥2.5 A**, and the tutorial includes an **undervoltage check** (`vcgencmd get_throttled` → expect `0x0`). Official PSU cable is the default; right-angle is the documented alternative. Optional fan transistor/GPIO control kept as a BONUS mission. Updates A5.

**B7 — Offline deliverable vs online pip/apt install. ADOPTED w/ CLARIFICATION.**
- Clarification of intent: "offline-usable" in the brief governs the **tutorial DOCUMENT** (it opens and works with no live internet / no CDN / no external lookups while building). It does **not** mean the build needs no network — the device is a *calendar that fetches ICS over the internet*, so **home Wi-Fi is a hard prerequisite** and is stated up front in the pre-flight checklist.
- Adopted hardening: ship a **pinned `requirements.txt`** (exact versions) **and** vendor a **local wheelhouse** (`vendor/wheels/`) in the repo so `pip install --no-index --find-links` works even if PyPI is unreachable, giving an offline-reinstall path. apt packages are listed with exact names; first install needs network (expected). Updates A3.

**B8 — v1/v2 scope ambiguity. ADOPTED.** **v1 (Weekend 1) is the required, complete, celebrated build** = the working portrait Cyborg calendar appliance with its own success criteria + BOOYAH certificate. **v2 (Weekend 2) is separate level-up chapters** (weather, meals, chores, touch) each with independent success criteria. Weather/meals/chores are **explicitly NOT part of the minimum successful build.** Updates C3/§E/§F.

## Non-blocking — resolutions
- **NB1 git-pull-on-cron brittle. ADOPTED:** default update path is a **manual "Update Cyborg" mission**; optional automation only pulls **tagged releases** and keeps the previous known-good checkout for one-command rollback. (Deviates from PRD §6 cron-pull; brief gives latitude; safer for a family appliance.)
- **NB2 weather degradation. ADOPTED:** v2 caches last weather response + timestamp; shows stale/offline weather state without ever blocking calendar render.
- **NB3 audio rate limit concrete. ADOPTED & made testable:** BOOYAH fires **≤1 per app-load/boot event**, and for refresh/recovery events **no more than once per 10 minutes** (matches PRD §10.6). Encoded as a constant + unit-tested.
- **NB4 mounting safety. ADOPTED:** mounting mission gets a checklist: screw length vs wall depth (fridge-side caution), stud/anchor rating, HDMI/power **cable service loop + strain relief**, **fan airflow/ventilation clearance**, and **service access** for SD/USB swap. Photo-slot markers added.

## Suggestions — resolutions
- **S1 source-of-truth wiring table. ADOPTED** → §H below (physical pin · BCM · voltage · device · mission level).
- **S2 boot-time health page. ADOPTED:** the fetch service exposes a local **`/health`** endpoint + a simple status page (calendar fetch status, USB mount, LKG age, clock/TZ, network, undervoltage) — a novice troubleshooting anchor referenced throughout the tutorial.
- **S3 "success without v2" certificate. ADOPTED:** explicit v1 completion checkpoint + "BOOYAH! You built Cyborg (v1)" certificate, independent of v2.

---

## §H. Source-of-truth WIRING TABLE (physical pin · BCM · voltage · device · level)

| Device | Physical pin(s) | BCM / signal | Voltage | Mission level | Notes |
| :- | :- | :- | :- | :- | :- |
| **5 V fan (+)** | Pin 4 | 5 V rail | 5 V | CORE | Always-on power rail, NOT GPIO-switched. ≤0.1 A fan + guard. |
| **5 V fan (−)** | Pin 6 | GND | — | CORE | Strain-relieved Dupont. |
| **DS3231 VCC** | Pin 1 | 3V3 | 3.3 V | CORE (Level-Up) | RTC powered from 3V3, NOT 5 V. |
| **DS3231 GND** | Pin 9 | GND | — | CORE (Level-Up) | |
| **DS3231 SDA** | Pin 3 | GPIO2 / I2C SDA | 3.3 V | CORE (Level-Up) | Enable I2C via `raspi-config`. |
| **DS3231 SCL** | Pin 5 | GPIO3 / I2C SCL | 3.3 V | CORE (Level-Up) | Occupies GPIO3 → wake-from-halt trick unavailable. |
| **Shutdown button (a)** | Pin 11 | GPIO17 | 3.3 V logic | BONUS | Soft-shutdown via gpio-monitor script; internal pull-up. |
| **Shutdown button (b)** | Pin 14 | GND | — | BONUS | Button bridges GPIO17→GND when pressed. |
| **Speaker** | — | 3.5 mm jack (or USB) | — | CORE | Not a GPIO device; powered separately. |

**Pin-safety rule (printed in the doc):** never bridge a 5 V pin to a 3.3 V or GND pin; double-check pin numbering against the printed header diagram before every connection. RTC and shutdown-button missions are wired one at a time, verified, then the next.

## §I. Pi 3B PERFORMANCE CONTRACT (the R1 ceiling, made buildable + testable)

The build MUST satisfy all of these; the tutorial verifies each:
1. **No compositor / no desktop environment.** Xorg + Openbox only; `unclutter` hides the cursor.
2. **GPU memory split:** `gpu_mem=128` in `/boot/firmware/config.txt` (enough for 1080p Chromium video decode, leaves RAM for the app). Verify with `vcgencmd get_mem gpu`.
3. **Chromium flags:** `--kiosk --noerrdialogs --disable-infobars --incognito --disable-extensions --disable-gpu-compositing --disable-features=Translate --check-for-update-interval=31536000 --overscroll-history-navigation=0` + `--force-device-scale-factor=1`. No background tabs.
4. **Render budget:** static local HTML, **no JS framework, no build step**, **no CSS blur/filter/box-shadow-heavy/animation** (per §13 animation-free except discrete state-change), **agenda DOM capped** (e.g. ≤ N visible rows, older events virtualized/trimmed). Webfont weight capped (subset or system font fallback).
5. **Process isolation:** `cyborg-fetch.service` (Python) does all polling/parsing/disk I/O; Chromium only paints local cached JSON. Fetch service memory target **< 80 MB RSS**.
6. **Boot-to-kiosk RAM target:** steady-state free RAM **≥ 200 MB** after kiosk + fetch service are up (verify `free -m`). If not met → fallback ladder: reduce agenda rows → drop webfont → disable any v2 zone → (last resort) escalate BOM per R1.
7. **Steady-state acceptance:** holds agenda render + 5-min refresh + occasional audio cue for 24 h with no kiosk thrash (verify via `/health` LKG age advancing + no OOM in `journalctl`).

## §J. Updated assumptions registry (post-Codex)

| ID | Resolved value |
| :- | :- |
| A1 | Bookworm **Lite 32-bit + Xorg + Openbox + unclutter + Chromium** (single locked stack) |
| A2 | USB **ext4**, mount by UUID `nofail,noatime`, atomic writes, microSD read-only fallback |
| A3 | `icalendar` + `recurring-ical-events`, **pinned** in requirements.txt **+ vendored wheelhouse** |
| A4 | 3.5 mm powered speaker |
| A5 | 5 V **rail** (pin 4/6) always-on fan ≤0.1 A + guard; GPIO transistor control = BONUS |
| A6 | DS3231 CORE level-up, I2C GPIO2/3 |
| A7 | tentative dimmed, declined hidden (config-flippable) |
| A8 | Open-Meteo (no key), cached + stale state (v2) |
| A9 | local JSON on USB for chores/meals (v2) |
| A10 (new) | Shutdown button → GPIO17 (pin 11); GPIO3 wake unused (RTC owns it) |
| A11 (new) | Updates = manual mission; optional tagged-release pull w/ rollback |
| A12 (new) | `/health` endpoint + status page is a core troubleshooting anchor |

**All blocking issues resolved; zero items now require a human decision mid-build.**
