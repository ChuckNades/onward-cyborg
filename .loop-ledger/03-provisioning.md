# Artifact: systemd units + provisioning (v1) — `03-provisioning`

Branch: `impl/provisioning` (commit `05515b1`, 11 files, +567). Tests: 31 passed (26 + 5).
Mode: HEADLESS. Implementer = **codex/gpt-5.5**; cross-vendor reviewer = **gemini/
gemini-2.5-flash**; grade by **claude/relay**.

Contract: runtime entrypoint (`python -m cyborg_core --config`), cyborg-fetch.service
(Restart=always, ~30s recovery), kiosk autostart (portrait xrandr+xinput, unclutter, Chromium
§I flags -> 127.0.0.1:8765), CORE screen-off/on timers, BONUS GPIO17 shutdown button,
idempotent setup.sh w/ --dry-run, USB UUID nofail,noatime mount, microSD fallback seed, venv +
offline wheelhouse fallback, tests. Honors §B2/B4/B5/B6, §H, §I, A11/A12.

---

## CYCLE 1

### Step 1 — author (codex/gpt-5.5)
`cyborg_core/__main__.py`: network_check (socket), undervoltage_check (vcgencmd parse),
`run_cycles(service,n,sleep_fn)` testable poll loop w/ per-cycle exception isolation,
build_service, main (initial refresh + daemon poller + serve). `deploy/systemd/`:
cyborg-fetch.service (Restart=always/RestartSec=5, ProtectSystem=full + ReadWritePaths for USB/
fallback/config), screen-off/on .timer+.service (22:00 / 06:30, DPMS/xrandr/tvservice),
cyborg-shutdown-button.service. `deploy/openbox/autostart` (xrandr left + xinput 90° matrix +
unclutter + Chromium w/ all §I flags). `scripts/setup.sh` (idempotent set -euo pipefail,
--dry-run, apt, I2C, gpu_mem=128, USB UUID fstab nofail,noatime via blkid, fallback LKG seed,
rsync->/opt, venv + wheelhouse fallback, config.local from example, install+enable units,
xorg portrait conf, undervoltage check). `scripts/shutdown_button.py` (GPIO17 BCM pull-up,
1.5s hold, import-guarded). `tests/test_provisioning.py` (5: run_cycles determinism, unit
directives, §I flags, setup.sh structure+shellcheck-if-present, fstab UUID/nofail/noatime,
import-guard).
- **Sandbox test:** 31 passed (codex), independently re-verified by orchestrator (31 passed).
- Note: `python` absent (only python3); shellcheck not installed → that assert self-skips.

### Step 2 — review (gemini/gemini-2.5-flash) — DISPATCHED
Sent full source/semantics + tests + contract (no worktree). Pointed hard at the suspected big
miss: BOOT INTEGRATION — nothing configures console autologin + startx, and the kiosk user
`cyborg` has a `nologin` shell, so Openbox `autostart` may never launch on boot; plus
chromium-browser-vs-chromium binary name, ProtectSystem write paths, blkid first-ext4 risk,
screen timer XAUTHORITY reach.
- **gemini cycle-1 verdict: NEEDS-ANOTHER-CYCLE.** 1 BLOCKING (A/B): kiosk NEVER launches on
  boot — no console-autologin+startx, and kiosk user `cyborg` has `nologin` shell. NON-BLOCKING
  C/D/E/F all verified clean (ReadWritePaths ok, Restart ok, §I flags present, idempotent,
  shutdown button safe). SUGGESTION D: blkid first-ext4 pick risks wrong disk.

### Step 3 — author fix (codex/gpt-5.5, cycle 2)
Adopted both. Separated roles: `cyborg` = non-login SYSTEM user for cyborg-fetch.service ONLY;
new configurable `CYBORG_KIOSK_USER` (default `pi`) runs the graphical session. setup.sh now:
writes `getty@tty1.service.d/override.conf` (`agetty --autologin $KIOSK_USER`) + enables it;
installs guarded `startx` in the kiosk user's `.bash_profile`, `.xinitrc`=`exec openbox-session`,
and the Openbox `autostart` under the kiosk user's home; TEMPLATES the screen-off/on units
(`@CYBORG_KIOSK_USER@`/`@CYBORG_KIOSK_HOME@`) and renders them for the kiosk user; hardens USB
select to prefer `LABEL=CYBORG`, ERROR on ambiguous multiple ext4, single-ext4 fallback (doc:
`mkfs.ext4 -L CYBORG`); echoes the boot path. +2 tests (autologin drop-in, xinitrc/startx/
autostart under kiosk user, screen-unit user resolution, label-preferred/ambiguity USB).
Re-test: **33 passed**. Commit `a514a54`.

### Step 4 — grade (gemini cycle-2 + orchestrator)
**gemini cycle-2 verdict: GO** — "boot-integration issue fully resolved … full boot chain
established (autologin->startx->openbox-session->autostart->chromium) … user separation a
robust improvement … USB hardening addresses the suggestion." Orchestrator concurs; no shared
big misses. Grade: GO. (Residual = on-hardware functional test, which is the human's build step
— the deliverable is the tested code + tutorial, not a running device.)

### Step 5 — final approval (claude/relay)
Runtime entrypoint + systemd units + idempotent setup.sh with a real, reviewed boot chain;
§I Chromium flags + gpu_mem; USB UUID nofail,noatime + microSD fallback; CORE screen timers;
BONUS GPIO17 button. 33/33 tests. Zero blocking. **APPROVED.** Merged `impl/provisioning`
-> `main`.

deltas_adopted: cycle 2 — kiosk/service user separation + autologin+startx+xinitrc boot chain;
templated screen units; LABEL=CYBORG-safe USB selection. Cross-model signal: a per-file unit
review can pass while the SYSTEM-level boot wiring is missing — review the end-to-end chain,
not just each unit in isolation.

