#!/usr/bin/env bash
set -euo pipefail

# Cyborg provisioner — Raspberry Pi 5 + Touch Display 2 (7" DSI).
#
# Provisions the VALIDATED kiosk model (verified on hardware 2026-06-21):
#   Raspberry Pi OS Desktop -> lightdm desktop autologin (pi) -> lxsession/openbox
#   -> XDG autostart -> chromium --kiosk, with cyborg.service serving the app.
# Portrait is done at KMS (config.txt rotation=90), storage is the single SD card
# (no USB tier), browser is `chromium`. This REPLACES the old Pi 3B + Acer model
# (console autologin + startx + openbox autostart + USB /mnt/cyborg + gpu_mem +
# i2c + xrandr/touch-matrix rotation) — none of which matched the live hardware.
#
# Optional appliance features that are NOT wired in here because they were never
# validated on this hardware and remain hardware-stale: the overnight screen
# on/off timers (deploy/systemd/cyborg-screen-*.{service,timer} — still reference
# HDMI-1/.Xauthority from the old model) and the GPIO17 shutdown button
# (deploy/systemd/cyborg-shutdown-button.service; the Pi 5 also has an onboard
# power button). Wire them in only after a real provision + hardware test.
# See docs/deploy-notes.md.

DRY_RUN=0
KIOSK_USER="${CYBORG_KIOSK_USER:-pi}"
CACHE_DIR="${CYBORG_CACHE_DIR:-/opt/cyborg-core/cache}"
FALLBACK_DIR="${CYBORG_FALLBACK_DIR:-/opt/cyborg-core/fallback}"
BOOT_CONFIG="${CYBORG_BOOT_CONFIG:-/boot/firmware/config.txt}"
LIGHTDM_CONF="${CYBORG_LIGHTDM_CONF:-/etc/lightdm/lightdm.conf}"
DSI_OVERLAY="${CYBORG_DSI_OVERLAY:-dtoverlay=vc4-kms-dsi-ili9881-7inch,rotation=90}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() { printf 'Usage: %s [--dry-run]\n' "$0"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run]'
    for arg in "$@"; do printf ' %q' "$arg"; done
    printf '\n'
  else
    "$@"
  fi
}

ensure_line() {
  local path="$1" line="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] ensure line in %s: %s\n' "$path" "$line"
  elif [[ ! -f "$path" ]] || ! grep -Fxq "$line" "$path"; then
    printf '%s\n' "$line" | sudo tee -a "$path" >/dev/null
  fi
}

write_file() {
  local path="$1" content="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] write %s\n%s\n' "$path" "$content"
  else
    sudo install -d -m 0755 "$(dirname "$path")"
    printf '%s\n' "$content" | sudo tee "$path" >/dev/null
  fi
}

KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6 || true)"
if [[ -z "$KIOSK_HOME" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    KIOSK_HOME="/home/${KIOSK_USER}"
  else
    printf 'Kiosk user %s does not exist.\n' "$KIOSK_USER" >&2
    exit 1
  fi
fi

# --- packages (RPi OS Desktop already ships lightdm/lxsession/openbox) ---
run sudo apt-get update
run sudo apt-get install -y chromium python3 python3-venv python3-pip

# --- single-SD cache + fallback (no USB tier on this hardware) ---
run sudo install -d -m 0755 -o "$KIOSK_USER" -g "$KIOSK_USER" /opt/cyborg-core "$CACHE_DIR" "$FALLBACK_DIR"

sample_lkg='{"version":1,"fetched_at":"2026-06-17T00:00:00+00:00","events":[],"calendars":{}}'
if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[dry-run] seed last-known-good JSON at %s/last-known-good.json\n' "$FALLBACK_DIR"
elif [[ ! -f "${FALLBACK_DIR}/last-known-good.json" ]]; then
  printf '%s\n' "$sample_lkg" | sudo tee "${FALLBACK_DIR}/last-known-good.json" >/dev/null
  run sudo chown "$KIOSK_USER:$KIOSK_USER" "${FALLBACK_DIR}/last-known-good.json"
fi

# --- python venv + deps (service runs from the repo checkout, as the live Pi does) ---
run sudo -u "$KIOSK_USER" python3 -m venv "${REPO_DIR}/.venv"
if [[ -d "${REPO_DIR}/vendor/wheels" ]]; then
  run sudo -u "$KIOSK_USER" "${REPO_DIR}/.venv/bin/pip" install --no-index --find-links "${REPO_DIR}/vendor/wheels" -r "${REPO_DIR}/requirements.txt"
else
  run sudo -u "$KIOSK_USER" "${REPO_DIR}/.venv/bin/pip" install -r "${REPO_DIR}/requirements.txt"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[dry-run] install config.local.toml from config.example.toml if absent\n'
elif [[ ! -f "${REPO_DIR}/config.local.toml" ]]; then
  install -m 0640 "${REPO_DIR}/config.example.toml" "${REPO_DIR}/config.local.toml"
fi

# --- display: portrait via KMS rotation overlay (Pi 5 ignores gpu_mem; no i2c) ---
ensure_line "$BOOT_CONFIG" "$DSI_OVERLAY"

# --- boot/kiosk: lightdm desktop autologin + XDG autostart launcher ---
ensure_line "$LIGHTDM_CONF" "[Seat:*]"
ensure_line "$LIGHTDM_CONF" "autologin-user=${KIOSK_USER}"
run sudo install -d -m 0755 -o "$KIOSK_USER" -g "$KIOSK_USER" "${KIOSK_HOME}/.config/autostart"
run sudo install -m 0644 -o "$KIOSK_USER" -g "$KIOSK_USER" "${REPO_DIR}/deploy/autostart/cyborg-kiosk.desktop" "${KIOSK_HOME}/.config/autostart/cyborg-kiosk.desktop"

# --- cyborg.service (serves the app; runs from the checkout as the kiosk user) ---
cyborg_unit="[Unit]
Description=Cyborg core
After=network-online.target
Wants=network-online.target
[Service]
User=${KIOSK_USER}
WorkingDirectory=${REPO_DIR}
ExecStart=${REPO_DIR}/.venv/bin/python -m cyborg_core --config config.local.toml
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target"
write_file /etc/systemd/system/cyborg.service "$cyborg_unit"

run sudo systemctl daemon-reload
run sudo systemctl enable cyborg.service

printf 'Boot model: lightdm autologin (%s) -> desktop -> XDG autostart -> chromium kiosk; cyborg.service serves http://localhost:8765/. Portrait via %s. Reboot to start.\n' "$KIOSK_USER" "$DSI_OVERLAY"

if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd get_throttled
else
  printf 'vcgencmd unavailable here; on the Pi expect: throttled=0x0\n'
fi
