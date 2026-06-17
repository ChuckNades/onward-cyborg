/* app.js — data fetch + DOM-light render for the Cyborg portrait kiosk.
 *
 * Renders ONLY local cached data from the localhost fetch/cache service; the browser never
 * touches the internet. All theming/celebration/audio is delegated to CyborgTheme (theme.js)
 * and is passed ONLY system state (staleness tier + pending_signal) — never event content.
 */
(function () {
  "use strict";

  var POLL_MS = 60000;            // re-fetch the local cache every 60s (independent of render)
  var MAX_VISIBLE_ROWS = 14;      // DOM-light cap (Pi 3B perf contract section I, item 4)
  var CLOCK_TICK_MS = 1000;
  var API_AGENDA = "/api/agenda";

  var els = {};
  var firstRenderCelebrated = false;

  function $(id) { return document.getElementById(id); }

  function cacheEls() {
    els.root = $("cyborg-root");
    els.clockTime = $("clock-time");
    els.clockDate = $("clock-date");
    els.nownext = $("nownext");
    els.nnStripe = $("nownext-stripe");
    els.nnTitle = $("nownext-title");
    els.nnWhen = $("nownext-when");
    els.list = $("agenda-list");
    els.empty = $("agenda-empty");
    els.chip = $("status-chip");
    els.mark = $("brand-mark");
  }

  // ---- time helpers: read the home-tz wall clock straight off the ISO offset string ----
  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  function wallFromIso(iso) {
    // iso like "2026-06-17T08:05:00-05:00" -> {h, m, datePart}
    var parts = String(iso).split("T");
    var datePart = parts[0] || "";
    var timePart = parts[1] || "00:00";
    return { h: parseInt(timePart.slice(0, 2), 10) || 0, m: timePart.slice(3, 5) || "00", date: datePart };
  }

  function fmt12(h, m) {
    var ampm = h >= 12 ? "PM" : "AM";
    var h12 = h % 12; if (h12 === 0) h12 = 12;
    return h12 + ":" + m + " " + ampm;
  }

  function weekdayDate(iso) {
    var d = new Date((iso || "").split("T")[0] + "T00:00:00");
    if (isNaN(d.getTime())) return "";
    var days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
    var mons = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
    return days[d.getDay()] + " · " + mons[d.getMonth()] + " " + d.getDate();
  }

  // ---- rendering (textContent + createElement only; no raw HTML strings, no framework) ----
  function eventTimeText(ev) {
    if (ev.all_day) return "ALL DAY";
    var w = wallFromIso(ev.start);
    return fmt12(w.h, w.m);
  }

  function renderNowNext(next) {
    if (!next) { els.nownext.hidden = true; return; }
    els.nownext.hidden = false;
    els.nnStripe.style.background = next.color || "#7e8c98";
    els.nnTitle.textContent = next.title || "Untitled";
    var when = next.all_day ? "All day" : (weekdayDate(next.start) + " · " + eventTimeText(next));
    els.nnWhen.textContent = when;
  }

  function renderAgenda(events) {
    var list = els.list;
    while (list.firstChild) list.removeChild(list.firstChild);
    var shown = events.slice(0, MAX_VISIBLE_ROWS);
    if (shown.length === 0) { els.empty.hidden = false; return; }
    els.empty.hidden = true;
    for (var i = 0; i < shown.length; i++) {
      var ev = shown[i];
      var li = document.createElement("li");
      li.className = "agenda-row" + (ev.dimmed ? " dimmed" : "");

      var stripe = document.createElement("span");
      stripe.className = "stripe";
      stripe.style.background = ev.color || "#7e8c98";

      var time = document.createElement("div");
      time.className = "row-time";
      if (ev.all_day) {
        var allday = document.createElement("span");
        allday.className = "allday";
        allday.textContent = "ALL DAY";
        time.appendChild(allday);
      } else {
        time.textContent = eventTimeText(ev);
      }

      var body = document.createElement("div");
      body.className = "row-body";
      var title = document.createElement("div");
      title.className = "row-title";
      title.textContent = ev.title || "Untitled";
      if (ev.tentative) {
        var badge = document.createElement("span");
        badge.className = "row-badge";
        badge.textContent = "tentative";
        title.appendChild(badge);
      }
      var cal = document.createElement("div");
      cal.className = "row-cal";
      cal.textContent = ev.calendar_name || ev.calendar_id || "";
      body.appendChild(title);
      body.appendChild(cal);

      li.appendChild(stripe);
      li.appendChild(time);
      li.appendChild(body);
      list.appendChild(li);
    }
  }

  function renderStatus(staleness, nowIso) {
    var tier = (staleness && staleness.tier) || "syncing";
    var age = staleness ? staleness.age_seconds : null;
    // Pass ONLY system state to the theming surface: tier + system clock + staleness age.
    var chip = CyborgTheme.staleChip(tier, nowIso, age); // theme.js builds the label itself
    if (!chip) { els.chip.hidden = true; els.chip.className = "status-chip"; return; }
    els.chip.hidden = false;
    els.chip.className = "status-chip " + (chip.cls || "");
    els.chip.textContent = chip.text;
  }

  function applyState(staleness, events) {
    var tier = (staleness && staleness.tier) || "syncing";
    var ready = !(tier === "syncing" && (!events || events.length === 0));
    els.root.dataset.state = ready ? "ready" : "syncing";
  }

  function render(data) {
    var events = data.events || [];
    applyState(data.staleness, events);
    if (data.now) {
      var w = wallFromIso(data.now);
      els.clockTime.textContent = fmt12(w.h, w.m);
      els.clockDate.textContent = weekdayDate(data.now);
    }
    renderNowNext(data.next);
    renderAgenda(events);
    renderStatus(data.staleness, data.now);

    // System-event signalling ONLY (never content-driven).
    if (!firstRenderCelebrated) { firstRenderCelebrated = true; CyborgTheme.signal("app-load"); }
    if (data.pending_signal) { CyborgTheme.signal(data.pending_signal); }
  }

  function refresh() {
    fetch(API_AGENDA, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
      .then(render)
      .catch(function () { /* keep last good render on the wall — never blank */ });
  }

  function tickClock() {
    // Lightweight liveness between polls; Pi browser tz is set to the home tz at provision time.
    var d = new Date();
    els.clockTime.textContent = fmt12(d.getHours(), pad2(d.getMinutes()));
  }

  function init() {
    cacheEls();
    CyborgTheme.applyBrandArt(els.mark);
    refresh();
    setInterval(refresh, POLL_MS);
    setInterval(tickClock, CLOCK_TICK_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
