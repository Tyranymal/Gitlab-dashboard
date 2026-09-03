/* Gemeinsamer Kern der drei Vorschau-Layouts: Dekodierung, Kennzahlen,
   Diff-Berechnung, Formatierung, Tooltip. Bewusst ohne Framework und ohne
   externe Chart-Library - die spaetere GitLab-Instanz hat im Browser-Kontext
   oft keinen Internetzugang, also wird auch produktiv nichts nachgeladen. */

const RUNS     = DATA.runs;
const TESTS    = DATA.tests;
const SERVICES = DATA.services;

/* Statuscodes: P pass · p pass mit fail-Tag · f bekannter Fail · F neuer Fail
   · '-' im Lauf nicht vorhanden */
const PASSISH = "Pp";
const FAILISH = "fF";

const CAT = {
  P: { key: "pass",    label: "Pass",              varName: "--st-pass" },
  p: { key: "passtag", label: "Pass, fail-Tag",    varName: "--st-passtag" },
  f: { key: "known",   label: "Fail, bekannt",     varName: "--st-known" },
  F: { key: "new",     label: "Fail, neu",         varName: "--st-new" },
};
/* Stapelreihenfolge von unten nach oben - so validiert */
const STACK = ["P", "p", "f", "F"];

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function counts(run) {
  const c = { P: 0, p: 0, f: 0, F: 0, total: 0 };
  for (const ch of run.s) {
    if (ch === "-") continue;
    c[ch]++; c.total++;
  }
  c.pass = c.P + c.p;
  c.fail = c.f + c.F;
  return c;
}

/* Diff gegen den zeitlich vorherigen Lauf - nicht gegen "gestern".
   Ausgefallene Naechte verschieben den Vergleich damit korrekt. */
function diff(prevRun, run) {
  const out = { regression: [], fixed: [], tagged: [], untagged: [], added: [], removed: [] };
  if (!prevRun) return out;
  const a = prevRun.s, b = run.s;
  for (let i = 0; i < b.length; i++) {
    const x = a[i], y = b[i];
    if (x === y) continue;
    const e = { i, from: x, to: y, test: TESTS[i] };
    if (x === "-")                                    out.added.push(e);
    else if (y === "-")                               out.removed.push(e);
    else if (PASSISH.includes(x) && FAILISH.includes(y)) out.regression.push(e);
    else if (FAILISH.includes(x) && PASSISH.includes(y)) out.fixed.push(e);
    else if (x === "F" && y === "f")                  out.tagged.push(e);
    else if (x === "f" && y === "F")                  out.untagged.push(e);
  }
  out.changed = out.regression.length + out.fixed.length + out.tagged.length
              + out.untagged.length + out.added.length + out.removed.length;
  return out;
}

const DIFF_META = {
  regression: { label: "neu fehlgeschlagen", varName: "--st-new" },
  fixed:      { label: "wieder gruen",       varName: "--st-pass" },
  tagged:     { label: "Tag gesetzt",        varName: "--st-known" },
  untagged:   { label: "Tag entfernt",       varName: "--st-passtag" },
  added:      { label: "neuer Test",         varName: "--accent" },
  removed:    { label: "Test entfallen",     varName: "--muted" },
};

/* Alle Diffs einmal vorberechnen - im echten Build macht das `nrd build`. */
const DIFFS = RUNS.map((r, i) => diff(i > 0 ? RUNS[i - 1] : null, r));
const COUNTS = RUNS.map(counts);

/* Der Prueflung ist ein Verbund von Microservices, jeder mit eigener Versionierung.
   Es gibt also kein "das Release", sondern je Service eine eigene Versionsspur. */

/* Zusammenhaengende Laufbereiche gleicher Version - je Service eine Liste. */
function versionSpans(service) {
  const spans = [];
  RUNS.forEach((r, i) => {
    const v = r.components ? r.components[service] : undefined;
    const last = spans[spans.length - 1];
    if (last && last.version === v) last.end = i;
    else spans.push({ version: v, start: i, end: i, idx: spans.length });
  });
  return spans;
}
const VSPANS_BY_SERVICE = Object.fromEntries(SERVICES.map((s) => [s, versionSpans(s)]));
const VCOLORS = ["--v1", "--v2", "--v3", "--v4"];
const VINKS   = ["--v-ink-1", "--v-ink-2", "--v-ink-3", "--v-ink-4"];

/* Welche Services haben zwischen zwei Laeufen die Version gewechselt? */
function componentDiff(prevRun, run) {
  const out = [];
  if (!prevRun) return out;
  SERVICES.forEach((name) => {
    const from = prevRun.components[name], to = run.components[name];
    if (from !== to) out.push({ name, from, to, kind: bumpKind(from, to) });
  });
  return out;
}

/* major / minor / patch - beeinflusst nur die Beschriftung, nicht die Farbe */
function bumpKind(from, to) {
  if (!from || !to) return "neu";
  const a = from.split("."), b = to.split(".");
  if (a[0] !== b[0]) return "major";
  if (a[1] !== b[1]) return "minor";
  return "patch";
}

const CDIFFS = RUNS.map((r, i) => componentDiff(i > 0 ? RUNS[i - 1] : null, r));

/* Gesamtzahl der Versionsspruenge je Service - Sortierschluessel und Kennzahl */
const SERVICE_BUMPS = Object.fromEntries(
  SERVICES.map((s) => [s, VSPANS_BY_SERVICE[s].length - 1]));

const WEEKDAY = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
function fmtDate(runId) {
  const d = new Date(runId + "T00:00:00");
  return WEEKDAY[d.getDay()] + " " + runId.slice(8) + "." + runId.slice(5, 7) + ".";
}
function fmtDateLong(runId) {
  return fmtDate(runId) + runId.slice(0, 4);
}
function fmtDuration(sec) {
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return h + ":" + String(m).padStart(2, "0") + " h";
}
function pct(n, total) { return total ? (100 * n / total).toFixed(1).replace(".", ",") + " %" : "–"; }

/* --- Tooltip ------------------------------------------------------------ */
const tip = document.createElement("div");
tip.className = "tip";
tip.setAttribute("role", "status");
document.body.appendChild(tip);

function showTip(html, ev) {
  tip.innerHTML = html;
  tip.dataset.open = "1";
  moveTip(ev);
}
function moveTip(ev) {
  const pad = 14, r = tip.getBoundingClientRect();
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + r.width  > innerWidth  - 8) x = ev.clientX - r.width  - pad;
  if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - pad;
  tip.style.left = Math.max(8, x) + "px";
  tip.style.top  = Math.max(8, y) + "px";
}
function hideTip() { tip.dataset.open = "0"; }

function runTipHtml(i) {
  const r = RUNS[i], c = COUNTS[i], d = DIFFS[i];
  const row = (code, n) =>
    `<dt><span class="swatch sw-${CAT[code].key}"></span>${CAT[code].label}</dt><dd>${n}</dd>`;
  const cd = CDIFFS[i];
  return `<div class="tip-title"><span>${fmtDateLong(r.run_id)}</span>
            <span class="mono muted">${cd.length ? cd.length + " Service-Updates" : "kein Update"}</span></div>
          <dl>
            ${row("P", c.P)}${row("p", c.p)}${row("f", c.f)}${row("F", c.F)}
            <dt style="padding-top:4px">Tests gesamt</dt><dd style="padding-top:4px">${c.total}</dd>
            <dt>Status-Wechsel</dt><dd>${d.changed || 0}</dd>
            <dt>neue Commits</dt><dd>${r.commits.length}</dd>
          </dl>`;
}

/* --- kleine DOM-Helfer -------------------------------------------------- */
function el(tag, attrs, children) {
  const NS = "http://www.w3.org/2000/svg";
  const svgTags = /^(svg|g|rect|line|text|path|circle|polyline|title)$/;
  const node = svgTags.test(tag) ? document.createElementNS(NS, tag)
                                 : document.createElement(tag);
  for (const k in (attrs || {})) {
    if (k === "text") node.textContent = attrs[k];
    else if (k === "html") node.innerHTML = attrs[k];
    else if (attrs[k] != null) node.setAttribute(k, attrs[k]);
  }
  (children || []).forEach((c) => node.appendChild(c));
  return node;
}
function testLabel(t) { return t.suite + " › " + t.name; }
