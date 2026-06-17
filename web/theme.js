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

  // In-character staleness chip copy, keyed ONLY on the system tier + a system timestamp label.
  function staleChip(tier, updatedLabel) {
    switch (tier) {
      case "fresh":
        return null; // no chip when fresh
      case "stale":
        return { text: "Cyborg synced · updated " + updatedLabel, cls: "tier-stale" };
      case "on-backup":
        return { text: "Cyborg is running on backup memory · updated " + updatedLabel, cls: "tier-on-backup" };
      case "syncing":
        return { text: "Cyborg is waking up… syncing the family calendar", cls: "tier-syncing" };
      default:
        return { text: "Cyborg · updated " + updatedLabel, cls: "" };
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
