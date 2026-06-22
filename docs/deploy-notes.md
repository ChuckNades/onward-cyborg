# Deploy notes — Pi 5 / Touch Display 2 kiosk

Hard-won gotchas from bringing the kiosk up on real hardware. Read before
re-provisioning or copying `config.example.toml`.

## Storage is a single SD card — no USB tier

This build boots from an SD card via a USB reader; there is **no separate USB
storage device** and nothing mounts at `/mnt/cyborg`. The "USB primary / SD
fallback" cache tiering in older configs is fiction on this hardware — treat all
storage as the one card.

- `config.example.toml` `[cache] primary_path` must point at a dir that **exists
  and is writable**, e.g. `/opt/cyborg-core/cache/last-known-good.json`. Create it:
  `sudo mkdir -p /opt/cyborg-core/cache && sudo chown pi /opt/cyborg-core/cache`.
- Why it matters: `store.py` `write_if_changed()` returns `False` (no write, no
  raise) when the primary parent dir is missing. The fetch reports OK, the store
  stays empty, `/api/agenda` serves `events: []`, and the front-end hangs on the
  syncing splash. Pointing primary at a real dir is the fix.
- **Latent asymmetry (harden later):** `read()` falls back to `fallback_path`, but
  writes only ever target `primary_path` — if primary is unwritable, nothing is
  written even to fallback.

## Chromium keyring prompt blocks the kiosk

An auto-login kiosk never unlocks the GNOME login keyring, so Chromium throws an
unlock dialog over the kiosk when it opens its keyring-backed password store.

- **Fix:** add `--password-store=basic` to the Chromium `Exec=` line in
  `~/.config/autostart/cyborg-kiosk.desktop` so Chromium bypasses gnome-keyring.
- Browser binary is `chromium` (NOT `chromium-browser`).

## Run command (module form)

```
cd ~/onward-cyborg && .venv/bin/python -m cyborg_core --config config.local.toml
```
`.venv/bin/cyborg_core` does not exist. `config.local.toml` is git-ignored and
carries the live iCloud read credential — never commit it, never echo the URL.

## Display orientation (DECIDED: v1 ships portrait via KMS rotation=90)

**Decision (Pete, 2026-06-21): v1 ships in PORTRAIT.** Portrait was the plan for
the larger display; a later landscape build on a smaller display was discussed.
That orientation choice is **deferred to future builds** — do not reopen it for
v1. The running, visually-verified state is portrait, and v1 locks it.

Portrait 720×1280 is produced by a **kernel (KMS) display rotation**, verified on
hardware 2026-06-21:

```
# /boot/firmware/config.txt
dtoverlay=vc4-kms-dsi-ili9881-7inch,rotation=90
```

**This line is load-bearing — do NOT remove it.** It is what rotates the panel
into portrait; the rendered UI was visually confirmed good with it present. The
panel scans landscape natively, so `rotation=90` is required for portrait.

- `web/style.css` is sized in `vw` units against a 1080-wide design that is the
  SAME 9:16 aspect as 720×1280, so it fills the rotated portrait surface with
  zero overflow. `index.html` viewport is `width=device-width` (was a hardcoded
  `width=1080`, the v1 overflow cause).
- **No compositor/xrandr rotation is used** (rotation is done once, at KMS).
  Stacking an `xrandr --rotate` on top of `rotation=90` would double-rotate.
- A future landscape build would: drop `rotation=90` (or set it to suit the mount),
  and re-target `style.css` to 1280×720 — a future-build task, not a v1 one.

## Kiosk launch model (verified on hardware)

The live Pi runs **Raspberry Pi OS Desktop → lxsession → openbox (WM) → Xorg
(X11, `DISPLAY=:0`)**, and the kiosk is launched by an **XDG autostart** entry,
NOT the bespoke openbox/startx path in `setup.sh`:

```
~/.config/autostart/cyborg-kiosk.desktop   # the ACTIVE launcher
  Exec=chromium --kiosk --start-fullscreen ... http://localhost:8765/
```

Canonical copy tracked at `deploy/autostart/cyborg-kiosk.desktop`. Two other
autostart files exist on the Pi but are **inert** (not the active launcher) and
should be ignored / cleaned up: `~/.config/openbox/autostart` (`chromium-browser`,
never fires under lxsession) and `~/.config/labwc/autostart` (Wayland; this
session is X11).

## Serving model (why a git pull deploys the UI)

`cyborg.service` runs from `~/onward-cyborg` (the git checkout), so the Python
server serves `web/` live from the working tree. UI fixes therefore deploy by:
`git pull` on the Pi → reload the kiosk (reboot, or relaunch Chromium). No
re-provision needed for `web/` changes — confirmed: the v1 layout fix deployed
this way (`a86a38c`) and was visually verified.

## Provisioning reconciliation (DONE 2026-06-21, re-target; re-provision pending)

`scripts/setup.sh` + `tests/test_provisioning.py` were re-targeted from the old
Pi 3B + Acer UT222Q model to the validated Pi 5 + Touch Display 2 model:

- **Storage:** single SD — `/opt/cyborg-core/{cache,fallback}`. Dropped the USB
  `/mnt/cyborg` mount + `blkid`/fstab probing.
- **Browser:** `chromium` (was `chromium-browser`).
- **Display:** portrait via KMS `rotation=90` in `config.txt`. Dropped `gpu_mem`
  (Pi 5 ignores it), `do_i2c` (off on the live Pi), and the `xrandr`/touch-matrix
  rotation.
- **Boot/kiosk:** lightdm desktop autologin (`autologin-user=pi`) + XDG autostart
  (`deploy/autostart/cyborg-kiosk.desktop`). Dropped the console-autologin →
  `startx` → `openbox-session` → openbox-autostart path.
- **Service:** `deploy/systemd/cyborg.service` (runs from the checkout as the
  kiosk user) — the validated live unit. Removed the stale `cyborg-fetch.service`
  (`/opt/cyborg-core`, `cyborg` user, `/mnt/cyborg`) and `deploy/openbox/autostart`.

**Validation:** the full suite passes on the Pi (Linux), and the setup.sh dry-run
output is asserted by the contract tests. NOT yet validated by an actual
wipe-and-reprovision (that would destroy the working unit) — per the forge SOP,
the first clean re-provision is the final proof. The live Pi remains hand-set-up.

**Kept but unwired (opt-in, not yet hardware-validated):** the overnight screen
on/off timers (`deploy/systemd/cyborg-screen-*`) and GPIO17 shutdown button
(`deploy/systemd/cyborg-shutdown-button.service`, `scripts/shutdown_button.py`).
These are real v1 design features but reference old-model details (HDMI-1,
`.Xauthority`) and the Pi 5 has an onboard power button. Wire them in only after a
real provision + a hardware test (e.g. confirm the screen actually blanks at 22:00).

## Note: store.py is Linux-only

`cyborg_core/store.py` uses `os.O_DIRECTORY` to fsync the cache dir after atomic
write — POSIX-only. The suite is 33/33 on the Pi (Linux); on Windows 4 store/http
tests fail with `AttributeError: module 'os' has no attribute 'O_DIRECTORY'`.
Expected; the runtime target is the Pi.

## Deploy rule

Git is the source of truth. The Pi changes only via `git pull`: develop on the
dev checkout → commit → push → `git pull` on the Pi → hardware-test. Hardware-only
work (layout against the panel, kiosk behavior, display rotation, GPIO, audio)
must be done on the Pi.
