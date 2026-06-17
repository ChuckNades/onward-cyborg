#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
USB_UUID="${CYBORG_USB_UUID:-}"
CYBORG_USER="${CYBORG_USER:-cyborg}"
CYBORG_GROUP="${CYBORG_GROUP:-cyborg}"
CYBORG_KIOSK_USER="${CYBORG_KIOSK_USER:-pi}"
INSTALL_DIR="${CYBORG_INSTALL_DIR:-/opt/cyborg-core}"
CONFIG_DIR="${CYBORG_CONFIG_DIR:-/etc/cyborg}"
MOUNT_POINT="${CYBORG_MOUNT_POINT:-/mnt/cyborg}"
CACHE_DIR="${MOUNT_POINT}/cyborg-cache"
FALLBACK_DIR="${INSTALL_DIR}/fallback"
BOOT_CONFIG="${CYBORG_BOOT_CONFIG:-/boot/firmware/config.txt}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="${INSTALL_DIR}/deploy"

usage() {
  printf 'Usage: %s [--dry-run] [--usb-uuid UUID]\n' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --usb-uuid)
      USB_UUID="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  DEPLOY_DIR="${REPO_DIR}/deploy"
fi

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %q' "$1"
    shift
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
  else
    "$@"
  fi
}

write_file() {
  local path="$1"
  local content="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] write %s\n%s\n' "$path" "$content"
  else
    sudo install -d -m 0755 "$(dirname "$path")"
    printf '%s\n' "$content" | sudo tee "$path" >/dev/null
  fi
}

ensure_line() {
  local path="$1"
  local line="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] ensure line in %s: %s\n' "$path" "$line"
  elif [[ ! -f "$path" ]] || ! grep -Fxq "$line" "$path"; then
    printf '%s\n' "$line" | sudo tee -a "$path" >/dev/null
  fi
}

user_home() {
  local user="$1"
  local home
  home="$(getent passwd "$user" | cut -d: -f6 || true)"
  if [[ -n "$home" ]]; then
    printf '%s\n' "$home"
  elif [[ "$DRY_RUN" -eq 1 ]]; then
    printf '/home/%s\n' "$user"
  else
    printf 'Kiosk user %s does not exist. Create it or set CYBORG_KIOSK_USER to a login-capable user.\n' "$user" >&2
    exit 1
  fi
}

render_install_unit() {
  local src="$1"
  local dest="$2"
  local content
  content="$(sed \
    -e "s|@CYBORG_KIOSK_USER@|${CYBORG_KIOSK_USER}|g" \
    -e "s|@CYBORG_KIOSK_HOME@|${CYBORG_KIOSK_HOME}|g" \
    "$src")"
  write_file "$dest" "$content"
  run sudo chmod 0644 "$dest"
}

chromium_package="chromium-browser"
if command -v apt-cache >/dev/null 2>&1 && ! apt-cache show chromium-browser >/dev/null 2>&1; then
  chromium_package="chromium"
fi

apt_packages=(
  xserver-xorg
  xinit
  openbox
  unclutter
  "$chromium_package"
  python3
  python3-venv
  python3-pip
  i2c-tools
  raspi-config
  x11-xserver-utils
  xinput
)

run sudo apt-get update
run sudo apt-get install -y "${apt_packages[@]}"

if ! id "$CYBORG_USER" >/dev/null 2>&1; then
  run sudo useradd --system --create-home --home-dir "/home/${CYBORG_USER}" --shell /usr/sbin/nologin "$CYBORG_USER"
fi
CYBORG_KIOSK_HOME="$(user_home "$CYBORG_KIOSK_USER")"

run sudo install -d -m 0755 -o "$CYBORG_USER" -g "$CYBORG_GROUP" "$INSTALL_DIR" "$FALLBACK_DIR"
run sudo install -d -m 0755 "$CONFIG_DIR" "$MOUNT_POINT"
run sudo install -d -m 0775 -o "$CYBORG_USER" -g "$CYBORG_GROUP" "$CACHE_DIR"

if command -v raspi-config >/dev/null 2>&1; then
  run sudo raspi-config nonint do_i2c 0
fi

if [[ -f "$BOOT_CONFIG" ]] || [[ "$DRY_RUN" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] set gpu_mem=128 in %s\n' "$BOOT_CONFIG"
  elif grep -q '^gpu_mem=' "$BOOT_CONFIG"; then
    run sudo sed -i 's/^gpu_mem=.*/gpu_mem=128/' "$BOOT_CONFIG"
  else
    ensure_line "$BOOT_CONFIG" "gpu_mem=128"
  fi
fi

if [[ -z "$USB_UUID" ]] && command -v blkid >/dev/null 2>&1; then
  # Format the cache stick with: sudo mkfs.ext4 -L CYBORG /dev/sdX1
  label_uuid="$(blkid -t LABEL=CYBORG -o value -s UUID | head -n 1 || true)"
  if [[ -n "$label_uuid" ]]; then
    USB_UUID="$label_uuid"
  else
    readarray -t ext4_uuids < <(blkid -t TYPE=ext4 -o value -s UUID || true)
    if [[ "${#ext4_uuids[@]}" -gt 1 ]]; then
      printf 'Multiple ext4 filesystems detected and none is labeled CYBORG. Re-run with --usb-uuid UUID.\n' >&2
      exit 1
    elif [[ "${#ext4_uuids[@]}" -eq 1 ]]; then
      USB_UUID="${ext4_uuids[0]}"
    fi
  fi
fi

if [[ -n "$USB_UUID" ]]; then
  fstab_line="UUID=${USB_UUID} ${MOUNT_POINT} ext4 nofail,noatime 0 2"
  ensure_line /etc/fstab "$fstab_line"
else
  printf 'No ext4 USB UUID detected; re-run with --usb-uuid UUID after formatting the stick.\n'
fi

sample_lkg='{"version":1,"fetched_at":"2026-06-17T00:00:00+00:00","events":[],"calendars":{}}'
if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[dry-run] seed fallback last-known-good JSON at %s/last-known-good.json\n' "$FALLBACK_DIR"
elif [[ ! -f "${FALLBACK_DIR}/last-known-good.json" ]]; then
  printf '%s\n' "$sample_lkg" | sudo tee "${FALLBACK_DIR}/last-known-good.json" >/dev/null
  run sudo chown "$CYBORG_USER:$CYBORG_GROUP" "${FALLBACK_DIR}/last-known-good.json"
fi

run sudo rsync -a --exclude .git --exclude .pytest_cache --exclude __pycache__ "$REPO_DIR"/ "$INSTALL_DIR"/
run sudo chown -R "$CYBORG_USER:$CYBORG_GROUP" "$INSTALL_DIR"
run sudo -u "$CYBORG_USER" python3 -m venv "${INSTALL_DIR}/.venv"

if [[ -d "${REPO_DIR}/vendor/wheels" ]]; then
  run sudo -u "$CYBORG_USER" "${INSTALL_DIR}/.venv/bin/pip" install --no-index --find-links "${REPO_DIR}/vendor/wheels" -r "${INSTALL_DIR}/requirements.txt"
else
  run sudo -u "$CYBORG_USER" "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[dry-run] install config.local.toml from config.example.toml if absent\n'
elif [[ ! -f "${CONFIG_DIR}/config.local.toml" ]]; then
  sudo install -m 0640 -o "$CYBORG_USER" -g "$CYBORG_GROUP" "${INSTALL_DIR}/config.example.toml" "${CONFIG_DIR}/config.local.toml"
fi

getty_override="[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${CYBORG_KIOSK_USER} --noclear %I \$TERM"
write_file /etc/systemd/system/getty@tty1.service.d/override.conf "$getty_override"

ensure_line "${CYBORG_KIOSK_HOME}/.bash_profile" 'if [ -z "$DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then exec startx; fi'
run sudo chown "$CYBORG_KIOSK_USER:$CYBORG_KIOSK_USER" "${CYBORG_KIOSK_HOME}/.bash_profile"
write_file "${CYBORG_KIOSK_HOME}/.xinitrc" 'exec openbox-session'
run sudo chown "$CYBORG_KIOSK_USER:$CYBORG_KIOSK_USER" "${CYBORG_KIOSK_HOME}/.xinitrc"

run sudo install -m 0644 "${DEPLOY_DIR}/systemd/cyborg-fetch.service" /etc/systemd/system/cyborg-fetch.service
render_install_unit "${DEPLOY_DIR}/systemd/cyborg-screen-off.service" /etc/systemd/system/cyborg-screen-off.service
run sudo install -m 0644 "${DEPLOY_DIR}/systemd/cyborg-screen-off.timer" /etc/systemd/system/cyborg-screen-off.timer
render_install_unit "${DEPLOY_DIR}/systemd/cyborg-screen-on.service" /etc/systemd/system/cyborg-screen-on.service
run sudo install -m 0644 "${DEPLOY_DIR}/systemd/cyborg-screen-on.timer" /etc/systemd/system/cyborg-screen-on.timer
run sudo install -m 0644 "${DEPLOY_DIR}/systemd/cyborg-shutdown-button.service" /etc/systemd/system/cyborg-shutdown-button.service
run sudo install -d -m 0755 -o "$CYBORG_KIOSK_USER" -g "$CYBORG_KIOSK_USER" "${CYBORG_KIOSK_HOME}/.config/openbox"
run sudo install -m 0755 -o "$CYBORG_KIOSK_USER" -g "$CYBORG_KIOSK_USER" "${DEPLOY_DIR}/openbox/autostart" "${CYBORG_KIOSK_HOME}/.config/openbox/autostart"

touch_matrix='xinput set-prop "${CYBORG_TOUCH_DEVICE:-Acer UT222Q}" "Coordinate Transformation Matrix" 0 -1 1 1 0 0 0 0 1'
write_file "/etc/X11/xorg.conf.d/99-cyborg-portrait.conf" 'Section "Monitor"
    Identifier "HDMI-1"
    Option "Rotate" "left"
EndSection'
printf 'Persisted touch transform command: %s\n' "$touch_matrix"

run sudo systemctl daemon-reload
run sudo systemctl enable getty@tty1.service
run sudo systemctl enable cyborg-fetch.service
run sudo systemctl enable cyborg-screen-off.timer
run sudo systemctl enable cyborg-screen-on.timer
run sudo systemctl enable cyborg-shutdown-button.service

printf 'Boot path configured: autologin tty1 (%s) -> startx -> openbox-session -> Openbox autostart -> Chromium kiosk.\n' "$CYBORG_KIOSK_USER"

if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd get_throttled
else
  printf 'vcgencmd unavailable here; on the Pi expect: throttled=0x0\n'
fi
