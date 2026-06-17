# Cyborg build tutorial (v1 + v2)

**Open it:** double-click `docs/tutorial/index.html` — it opens in any browser with **no internet
needed**. It is fully self-contained (no CDN, no web fonts, no external resources). Your step
checkboxes save in the browser automatically.

**Print / PDF for the workbench:** click **🖨️ Print / Save as PDF** at the top (or `Ctrl/Cmd+P`)
→ *Save as PDF*. The print stylesheet expands every troubleshooting drop-down and avoids breaking
diagrams across pages.

## What's inside
- **Pre-flight:** BOM, tools, getting your Apple/iCloud public **ICS** link, the Golden Safety Rules,
  and the 40-pin header map.
- **Weekend 1 (v1) — 9 missions:** flash & boot → cooling fan → DS3231 clock → install the code &
  calendar → USB last-known-good cache → portrait kiosk & auto-start → BOOYAH audio → wall mount →
  power button & screen schedule. Each step has an exact command, a green **"you'll know it worked"**
  check, and an inline **"if it didn't…"** fix. Ends with a v1 acceptance checklist + certificate.
- **Weekend 2 (v2) — the next level:** the zoned household hub (weather + meal of the day · the v1
  calendar anchor · touch chore chart · week's meals), documented as a build-on-v1 blueprint with the
  exact backend/frontend seams, honoring the §13 theming invariant and the Pi 3B performance budget.
- **Reference:** Troubleshooting HQ, command cheat-sheet, badge checklist.

## How it maps to the tested code (all sandbox-tested, in this repo)
- `cyborg_core/` — the fetch/cache backend (ICS parse, §12 event cases, atomic USB→microSD
  last-known-good store, `/api/agenda`, `/health`, §13 BOOYAH signaling). Run on the Pi via
  `python -m cyborg_core --config /etc/cyborg/config.local.toml`.
- `web/` — the portrait kiosk (vanilla HTML/CSS/JS, DOM-light, animation-free).
- `deploy/` + `scripts/setup.sh` — the systemd units + idempotent provisioner the tutorial drives.
- `config.example.toml` — the settings template you copy to `config.local.toml`.

The labeled wiring/assembly diagrams (mermaid source) live in
[`docs/diagrams/wiring.md`](../diagrams/wiring.md); the tutorial embeds offline ASCII versions of the
same connections (header map, fan, RTC, button). `📷 PHOTO SLOT` markers show where to tape in real
build photos.
