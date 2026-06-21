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

## Display orientation (LOCKED: portrait, panel-native)

Panel = Touch Display 2, 7" DSI, **portrait-native 720×1280**. v1 runs portrait
with **no rotation** — the kiosk fills the panel's native orientation directly.

- `web/style.css` is sized in `vw` units against a 1080-wide design that is the
  SAME 9:16 aspect as 720×1280, so it scales to fill any portrait DSI panel with
  zero overflow. `index.html` viewport is `width=device-width` (was a hardcoded
  `width=1080`, the v1 overflow cause).
- The `xrandr --output "$HDMI_OUTPUT" --rotate left` + Acer touch matrix lines in
  `deploy/openbox/autostart` are **no-ops on this hardware** — they target
  `HDMI-1` / `Acer UT222Q`, but the panel is DSI. That is *why* portrait "just
  works." They are retained only because the current test suite asserts them
  (see reconciliation debt below); do not rely on them.

## Serving model (why a git pull deploys the UI)

`cyborg.service` runs from `~/onward-cyborg` (the git checkout), so the Python
server serves `web/` live from the working tree. UI fixes therefore deploy by:
`git pull` on the Pi → reload Chromium (or `sudo systemctl restart cyborg` if the
backend changed). No re-provision needed for `web/` changes.

## OPEN: Pi 5 / Touch Display 2 provisioning reconciliation (debt)

`scripts/setup.sh`, `deploy/openbox/autostart`, and `tests/test_provisioning.py`
still encode the ORIGINAL Pi 3B + Acer UT222Q target and have NOT been re-run on
the current hardware (the live Pi was hand-provisioned). Stale assumptions:

- USB cache mount at `/mnt/cyborg` (fiction on single-SD-card build; `config.example.toml`
  was repointed to `/opt/cyborg-core/cache`, but `setup.sh` still creates/mounts
  `/mnt/cyborg` and the contract test asserts it).
- `chromium-browser` binary (trixie ships `chromium`).
- Landscape→portrait rotation + Acer touch matrix (no-ops; the panel is DSI portrait-native).

These are intentionally NOT silently rewritten: re-targeting them changes the
test contract and cannot be validated without a full re-provision on the Pi.
Treat as the next provisioning pass, validated on hardware before the repo claims
it works (forge-build SOP: authored is not shipped).

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
