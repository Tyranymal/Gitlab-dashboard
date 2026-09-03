#!/usr/bin/env python3
"""Erzeugt eine synthetische Nachtlauf-Historie fuer die Layout-Vorschauen.

Kein Robot Framework noetig - die Struktur entspricht exakt dem, was
`nrd collect` spaeter aus einer echten output.xml erzeugt, nur eben erfunden.
Deterministisch (fester Seed), damit alle drei Vorschauseiten denselben
Datensatz zeigen und direkt vergleichbar sind.

Kompaktes Format: statt 60 x 214 Test-Objekten gibt es EINE Testliste und pro
Lauf einen String mit einem Zeichen je Test:
    P = pass            p = pass, aber fail-Tag gesetzt (Tag-Kandidat)
    f = fail mit Tag    F = fail ohne Tag (neu/unerwartet)
    -  = Test in diesem Lauf nicht vorhanden
Das ist dieselbe Idee wie die spaetere Trennung index.json / runs/*.json:
die Uebersicht bleibt klein, Details kommen erst bei Bedarf.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260903
NIGHTS = 60
LAST_NIGHT = datetime(2026, 9, 3, 1, 0, tzinfo=timezone(timedelta(hours=2)))

# Suiten eines fiktiven, aber plausiblen Geraete-Testprojekts
SUITES = [
    ("Smoke", 18),
    ("Device.Connection", 24),
    ("Device.Firmware", 21),
    ("Measurement.Calibration", 31),
    ("Measurement.Streaming", 27),
    ("Requirements.Traceability", 16),
    ("API.Rest", 29),
    ("API.Websocket", 19),
    ("UI.Configuration", 20),
]  # Summe: 205, wird unten auf 214 aufgefuellt

TEST_VERBS = [
    "Verify", "Check", "Ensure", "Validate", "Reject", "Recover From",
    "Detect", "Report", "Persist", "Reset",
]
TEST_NOUNS = [
    "Sensor Timeout", "Baud Rate Switch", "Checksum Mismatch", "Cold Start",
    "Firmware Rollback", "Session Handshake", "Drift Compensation",
    "Sample Rate 48 kHz", "Threshold Alarm", "Config Import", "Config Export",
    "Idle Reconnect", "Bulk Transfer", "Token Refresh", "Partial Payload",
    "Unit Conversion", "Temperature Offset", "Multi Channel Sync",
    "Requirement Link", "Watchdog Trip", "Power Cycle", "Zero Point",
    "Range Overflow", "Locale Fallback", "Concurrent Access",
]

COMMIT_SUBJECTS = [
    "Warte-Keyword fuer Firmware-Handshake robuster gemacht",
    "Neue Testfaelle fuer Kalibrier-Offset ergaenzt",
    "Resource: Timeout von 30s auf 45s erhoeht",
    "fail:DEV-{n} Tag entfernt, Test laeuft wieder",
    "fail:DEV-{n} Tag gesetzt (Firmware-Bug, siehe Ticket)",
    "Library: Reconnect-Logik in DeviceKeywords vereinheitlicht",
    "Testdaten fuer Streaming-Suite aktualisiert",
    "Flaky Sleep durch Wait Until Keyword Succeeds ersetzt",
    "Requirements-Mapping auf neue REQ-IDs umgestellt",
    "Setup: VM-Provisionierung nutzt jetzt Poetry-Lockfile",
    "Doku der Suite-Metadaten auf ui-shell {v} gehoben",
    "Aufraeumen: ungenutzte Variablen aus common.resource entfernt",
    "Retry fuer Websocket-Verbindungsaufbau ergaenzt",
    "Assertion-Message bei Range Overflow praezisiert",
]

AUTHORS = ["m.keller", "s.brandt", "j.pohl", "a.wieland", "t.ruf"]

# Der Pruefling ist kein Monolith mit einer Release-Nummer, sondern ein Verbund
# von Microservices mit je eigener Versionierung. Jeder Service springt zu seinen
# eigenen Zeitpunkten - genau das soll das Dashboard sichtbar machen.
SERVICES = [
    ("api-gateway",     "3.4.0"),
    ("auth-service",    "2.14.2"),
    ("device-registry", "1.9.7"),
    ("ingest-service",  "5.2.1"),
    ("calibration-svc", "0.31.4"),
    ("reporting-svc",   "4.0.9"),
    ("ui-shell",        "12.6.0"),
]


def bump(version: str, kind: str) -> str:
    major, minor, patch = (int(x) for x in version.split("-")[0].split("."))
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "major":
        return f"{major + 1}.0.0"
    return f"{major}.{minor}.{patch + 1}"


def service_versions(rng: random.Random, nights: int) -> dict[str, list[str]]:
    """Je Service eine Versionsspur ueber alle Naechte. Die Sprungzeitpunkte sind
    bewusst unabhaengig voneinander - kein gemeinsamer Release-Takt."""
    tracks: dict[str, list[str]] = {}
    for name, start in SERVICES:
        cur = start
        track = []
        # jeder Service hat sein eigenes Tempo
        rate = rng.choice([0.03, 0.05, 0.08, 0.12])
        for night in range(nights):
            if night > 0 and rng.random() < rate:
                kind = "major" if rng.random() < 0.08 else ("minor" if rng.random() < 0.35 else "patch")
                cur = bump(cur, kind)
            track.append(cur)
        tracks[name] = track
    return tracks


def make_tests(rng: random.Random) -> list[dict]:
    tests: list[dict] = []
    used: set[str] = set()
    for suite, count in SUITES:
        for _ in range(count):
            while True:
                name = f"{rng.choice(TEST_VERBS)} {rng.choice(TEST_NOUNS)}"
                if f"{suite}.{name}" not in used:
                    break
            used.add(f"{suite}.{name}")
            tests.append({"suite": suite, "name": name})
    # auf 214 auffuellen
    while len(tests) < 214:
        suite = rng.choice(SUITES)[0]
        name = f"{rng.choice(TEST_VERBS)} {rng.choice(TEST_NOUNS)} {len(tests)}"
        tests.append({"suite": suite, "name": name})
    return tests


def main() -> None:
    rng = random.Random(SEED)
    tests = make_tests(rng)
    tracks = service_versions(rng, NIGHTS)
    # Die Regression haengt an einem konkreten Service-Sprung, nicht an "dem Release":
    # calibration-svc bekommt in Nacht 38 einen erzwungenen Minor-Sprung.
    for night in range(38, NIGHTS):
        tracks["calibration-svc"][night] = bump(tracks["calibration-svc"][37], "minor") \
            if night < 50 else bump(bump(tracks["calibration-svc"][37], "minor"), "patch")
    n = len(tests)

    # Grundzustand: die meisten Tests laufen. Ein Teil ist dauerhaft kaputt und
    # traegt dafuer einen fail:-Tag - das ist der grosse "bekannt"-Block.
    known_broken = set(rng.sample(range(n), 78))      # fail + Tag
    tagged = set(known_broken)
    # zwei Tests tragen den Tag, laufen aber wieder durch (Tag-Kandidaten)
    tag_candidates = set(rng.sample([i for i in range(n) if i not in tagged], 2))
    tagged |= tag_candidates

    flaky = set(rng.sample([i for i in range(n) if i not in known_broken], 9))
    # Regressionscluster: bricht mit 24.3.1 auf und wird spaeter geflickt
    regression = rng.sample(
        sorted({i for i in range(n) if tests[i]["suite"].startswith("Measurement")}
               - known_broken), 11)
    # Tests, die es erst ab Nacht 30 gibt bzw. ab Nacht 45 nicht mehr
    added_later = set(rng.sample([i for i in range(n) if i not in known_broken], 6))
    removed_later = set(rng.sample(
        [i for i in range(n) if i not in known_broken and i not in added_later], 4))

    runs = []
    prev_sha = "%08x" % rng.getrandbits(32)
    ticket = 400
    for night in range(NIGHTS):
        date = LAST_NIGHT - timedelta(days=(NIGHTS - 1 - night))
        # zwei ausgefallene Naechte - der Diff muss den vorherigen *Lauf*
        # vergleichen, nicht "gestern"
        if night in (17, 41):
            continue

        components = {name: tracks[name][night] for name, _ in SERVICES}
        chars = []
        for i in range(n):
            if i in added_later and night < 30:
                chars.append("-")
                continue
            if i in removed_later and night >= 45:
                chars.append("-")
                continue
            if i in known_broken:
                # ein paar bekannte Fails werden im Lauf der Zeit repariert
                if night >= 46 and i % 17 == 0:
                    chars.append("P")
                else:
                    chars.append("f")
                continue
            if i in tag_candidates:
                chars.append("p")
                continue
            if i in regression and 38 <= night < 50:
                chars.append("F")
                continue
            if i in flaky and rng.random() < 0.22:
                chars.append("F")
                continue
            # Grundrauschen: gelegentlich ein echter neuer Fail
            if rng.random() < 0.004:
                chars.append("F")
                continue
            chars.append("P")

        sha = "%08x" % rng.getrandbits(32)
        commits = []
        for _ in range(rng.randint(0, 6)):
            ticket += rng.randint(1, 7)
            subject = rng.choice(COMMIT_SUBJECTS).format(n=ticket, v=components["ui-shell"])
            commits.append({
                "sha": "%08x" % rng.getrandbits(32),
                "author": rng.choice(AUTHORS),
                "subject": subject,
            })

        runs.append({
            "run_id": date.strftime("%Y-%m-%d"),
            "started_at": date.isoformat(),
            "elapsed_s": rng.randint(6800, 9400),
            "components": components,
            "version_source": "metadata" if night > 12 else "suite_doc",
            "pipeline_id": str(48210 + night * 7),
            "sha": sha,
            "prev_sha": prev_sha,
            "commits": commits,
            "s": "".join(chars),
        })
        prev_sha = sha

    data = {
        "schema": 1,
        "generated": "demo",
        "services": [name for name, _ in SERVICES],
        "tests": tests,
        "runs": runs,
        "legend": {
            "P": "pass",
            "p": "pass, fail-Tag gesetzt",
            "f": "fail, bekannt (fail-Tag)",
            "F": "fail, neu",
            "-": "nicht im Lauf",
        },
    }
    out = Path(__file__).with_name("demo-data.json")
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    last = runs[-1]["s"]
    print(f"{len(runs)} Laeufe, {n} Tests -> {out} ({out.stat().st_size/1024:.0f} KB)")
    print("letzter Lauf:", {k: last.count(k) for k in "Ppf F-".replace(" ", "")})


if __name__ == "__main__":
    main()
