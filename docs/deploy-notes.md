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

## Deploy rule

Git is the source of truth. The Pi changes only via `git pull`: develop on the
dev checkout → commit → push → `git pull` on the Pi → hardware-test. Hardware-only
work (layout against the panel, kiosk behavior, display rotation, GPIO, audio)
must be done on the Pi.
