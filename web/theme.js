/* theme.js — the ONLY theming / celebration / BOOYAH-audio surface.
 *
 * PRD section 13 invariant (load-bearing): this module consumes ONLY fixed SYSTEM state —
 * staleness tier strings and the three system-event signal strings. It must NEVER read,
 * classify, or branch on calendar event content. Enforced by tests/test_frontend_invariant.py
 * (a grep-able test that fails if this file references event-content fields).
 */
(function (global) {
  "use strict";

  // The three fixed SYSTEM signals — the ONLY triggers allowed to fire the BOOYAH cue.
  var SYSTEM_SIGNALS = ["app-load", "successful-refresh", "fetch-failure-recovery"];

  // Runtime-only assets live in the git-ignored assets/ dir. Repo ships NO trademarked art/audio.
  var BOOYAH_AUDIO_SRC = "/assets/booyah.mp3";
  var BRAND_ART_SRC = "/assets/cyborg-mark.png";

  var appLoadCelebrated = false;
  var audio = null;

  function getAudio() {
    if (audio === null) {
      try {
        audio = new Audio(BOOYAH_AUDIO_SRC);
        audio.preload = "auto";
      } catch (e) {
        audio = false; // no Audio support -> permanent silent fallback
      }
    }
    return audio;
  }

  function playBooyah() {
    var a = getAudio();
    if (!a) return;
    try {
      a.currentTime = 0;
      var p = a.play();
      if (p && typeof p.catch === "function") {
        p.catch(function () {}); // missing asset / autoplay policy -> silent, never throws
      }
    } catch (e) { /* silent fallback */ }
  }

  // Fire the BOOYAH cue ONLY for one of the three fixed system signals. Content can never reach here.
  function signal(systemEvent) {
    if (SYSTEM_SIGNALS.indexOf(systemEvent) === -1) return;
    if (systemEvent === "app-load") {
      if (appLoadCelebrated) return;
      appLoadCelebrated = true;
    }
    playBooyah();
  }

  // --- system-time helpers: the staleness label is built ONLY from system time (now ISO +
  //     staleness age in seconds). No caller-supplied free text, so no event content can leak
  //     into the theming surface (closes the staleChip-label loophole). ---
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function fmt12(h, m) {
    var ampm = h >= 12 ? "PM" : "AM";
    var h12 = h % 12; if (h12 === 0) h12 = 12;
    return h12 + ":" + m + " " + ampm;
  }
  function offsetMinutes(iso) {
    var m = String(iso).match(/([+-])(\d{2}):(\d{2})$/);
    if (!m) return 0;
    var sign = m[1] === "-" ? -1 : 1;
    return sign * (parseInt(m[2], 10) * 60 + parseInt(m[3], 10));
  }
  function updatedLabel(nowIso, ageSeconds) {
    if (ageSeconds == null) return "just now";
    var ms = Date.parse(nowIso) - ageSeconds * 1000;
    if (isNaN(ms)) return "recently";
    var local = new Date(ms + offsetMinutes(nowIso) * 60000); // home wall time via the ISO offset
    return fmt12(local.getUTCHours(), pad2(local.getUTCMinutes()));
  }

  // In-character staleness chip copy. Inputs are ONLY system state: the tier string, the
  // system clock (now ISO) and the staleness age in seconds. theme.js computes the label itself.
  function staleChip(tier, nowIso, ageSeconds) {
    var updatedLabel_ = updatedLabel(nowIso, ageSeconds);
    switch (tier) {
      case "fresh":
        return null; // no chip when fresh
      case "stale":
        return { text: "Cyborg synced · updated " + updatedLabel_, cls: "tier-stale" };
      case "on-backup":
        return { text: "Cyborg is running on backup memory · updated " + updatedLabel_, cls: "tier-on-backup" };
      case "syncing":
        return { text: "Cyborg is waking up… syncing the family calendar", cls: "tier-syncing" };
      default:
        return { text: "Cyborg · updated " + updatedLabel_, cls: "" };
    }
  }

  // Upgrade the placeholder mark to runtime brand art (git-ignored assets/) if present. Silent fallback.
  function applyBrandArt(markEl) {
    if (!markEl) return;
    var probe = new Image();
    probe.onload = function () {
      markEl.style.backgroundImage = "url('" + BRAND_ART_SRC + "')";
      markEl.style.backgroundSize = "cover";
      markEl.classList.add("has-art");
    };
    probe.onerror = function () { /* keep the original placeholder glyph */ };
    probe.src = BRAND_ART_SRC;
  }

  global.CyborgTheme = {
    SYSTEM_SIGNALS: SYSTEM_SIGNALS,
    signal: signal,
    staleChip: staleChip,
    applyBrandArt: applyBrandArt
  };
})(window);
