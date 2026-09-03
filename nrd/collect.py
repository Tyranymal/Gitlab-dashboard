"""Liest eine Robot-Framework-`output.xml` und macht daraus einen Lauf.

Bewusst mit `xml.etree.ElementTree.iterparse` statt mit `robot.api`:

* Der Collector laeuft damit ohne installiertes Robot Framework - auch dort,
  wo nur die Artefakte ankommen und niemand die Suite ausfuehrt.
* `ExecutionResult` baut das komplette Modell inklusive aller Keywords und
  Log-Messages im Speicher auf. Eine reale `output.xml` mit 214 Tests hat
  schnell dreistellige MB; hier bleibt der Verbrauch flach, weil Keywords und
  Tests nach dem Lesen sofort verworfen werden.

Getestet gegen Robot 7 (`start`/`elapsed`, `<meta>`) und das aeltere Format
(`starttime`/`endtime`, `<metadata><item>`).
"""
from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from .model import (SOURCE_METADATA, SOURCE_MIXED, SOURCE_NONE, SOURCE_SUITE_DOC,
                    Run, CaseResult)

#: "1.2", "0.33.1", "12.7.0-rc1" - mindestens ein Punkt, damit eine nackte
#: Pipeline-Nummer nicht als Version durchgeht.
VERSION_RE = re.compile(r"^v?\d+\.\d+[\w.\-+]*$")

#: Versionszeile in der Suite-Dokumentation: "api-gateway: 3.5.1"
DOC_VERSION_RE = re.compile(
    r"^\s*([A-Za-z][\w.\-]*)\s*[:=]\s*(v?\d+\.\d+[\w.\-+]*)\s*$")


def _parse_time(status_el: ET.Element | None) -> tuple[str, float]:
    """(ISO-Startzeit, Dauer in Sekunden) aus einem <status>-Element.

    Robot >= 7 schreibt `start` (ISO) und `elapsed` (Sekunden), aeltere
    Versionen `starttime`/`endtime` im Format `%Y%m%d %H:%M:%S.%f`.
    """
    if status_el is None:
        return "", 0.0
    start = status_el.get("start")
    if start:
        return start, float(status_el.get("elapsed") or 0.0)
    st, et = status_el.get("starttime"), status_el.get("endtime")
    if not st:
        return "", 0.0
    fmt = "%Y%m%d %H:%M:%S.%f"
    started = datetime.strptime(st, fmt)
    elapsed = (datetime.strptime(et, fmt) - started).total_seconds() if et else 0.0
    return started.isoformat(), elapsed


def _suite_meta(suite_el: ET.Element) -> dict[str, str]:
    """Metadaten einer Suite - beide Schreibweisen."""
    meta = {}
    for el in suite_el.findall("meta"):                 # Robot >= 4
        if el.get("name"):
            meta[el.get("name")] = (el.text or "").strip()
    for el in suite_el.findall("metadata/item"):        # Robot 3
        if el.get("name"):
            meta[el.get("name")] = (el.text or "").strip()
    return meta


def _doc_versions(doc: str) -> dict[str, str]:
    """Versionszeilen aus einer Suite-Dokumentation."""
    out = {}
    for line in (doc or "").splitlines():
        m = DOC_VERSION_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2).lstrip("v")
    return out


def parse_output_xml(path: str | Path, services: list[str] | None = None) -> Run:
    """Ein Lauf aus einer output.xml. Wirft ValueError, wenn keine Tests drin sind.

    `services` schraenkt ein, welche Metadaten- und Doku-Eintraege als Service
    gelten; ohne Angabe zaehlt alles, was wie eine Version aussieht.
    """
    path = Path(path)
    results: list[CaseResult] = []
    meta: dict[str, str] = {}
    docs: list[str] = []
    suite_stack: list[str] = []
    generator = ""
    started_at, elapsed = "", 0.0
    in_statistics = False

    # "start" brauchen wir fuer den Suite-Pfad (Tests kommen vor </suite>),
    # "end" fuer alles andere.
    for event, el in ET.iterparse(str(path), events=("start", "end")):
        if event == "start":
            # <statistics> enthaelt selbst <suite>-Elemente (die Suite-Statistik).
            # Ohne diese Klammer zaehlen die als Suiten mit und ueberschreiben
            # am Ende Startzeit und Laufzeit des echten Wurzellaufs.
            if el.tag == "statistics":
                in_statistics = True
            elif in_statistics:
                pass
            elif el.tag == "suite":
                suite_stack.append(el.get("name") or "")
            elif el.tag == "robot":
                generator = el.get("generator") or ""
            continue

        if el.tag == "statistics":
            in_statistics = False
            el.clear()
            continue
        if in_statistics:
            continue

        if el.tag == "test":
            status_el = el.find("status")
            _, test_elapsed = _parse_time(status_el)
            results.append(CaseResult(
                # Die aeusserste Suite ist der Lauf selbst und traegt keine
                # Information - "Nightly.Device.Connection" waere in jeder
                # Zeile dasselbe Praefix.
                suite=".".join(suite_stack[1:]) or (suite_stack[-1] if suite_stack else ""),
                name=el.get("name") or "",
                status=(status_el.get("status") if status_el is not None else "") or "",
                tags=[t.text.strip() for t in el.findall("tag") if t.text],
                message=((status_el.text or "").strip() if status_el is not None else ""),
                elapsed_s=test_elapsed,
            ))
            el.clear()
        elif el.tag in ("kw", "for", "if", "try", "while", "msg", "iter"):
            el.clear()          # Keyword-Detail wird nicht gebraucht
        elif el.tag == "suite":
            meta.update(_suite_meta(el))
            doc_el = el.find("doc")
            if doc_el is not None and doc_el.text:
                docs.append(doc_el.text)
            if len(suite_stack) == 1:                   # aeusserste Suite endet
                started_at, elapsed = _parse_time(el.find("status"))
            suite_stack.pop()
            el.clear()

    if not results:
        raise ValueError(f"{path}: keine Tests in der output.xml")

    run = Run(
        run_id=(started_at[:10] if started_at else ""),
        started_at=started_at,
        elapsed_s=int(round(elapsed)),
        results=results,
        generator=generator,
    )
    run.components, run.version_source = resolve_versions(meta, docs, services)
    run.pipeline_id = meta.get("Pipeline", meta.get("pipeline", ""))
    return run


def resolve_versions(meta: dict[str, str], docs: list[str],
                     services: list[str] | None = None) -> tuple[dict[str, str], str]:
    """Service-Versionen aus Metadaten, ersatzweise aus der Suite-Doku.

    Metadaten gewinnen, weil sie ausdruecklich gesetzt sind; die Doku fuellt
    nur auf, was dort fehlt. Zurueck kommt auch, woher die Angaben stammen -
    im Dashboard steht das an den Versionen dran, damit niemand eine aus der
    Doku geschaetzte Version fuer einen Build-Fakt haelt.
    """
    def wanted(name: str) -> bool:
        return name in services if services else True

    from_meta = {k: v.lstrip("v") for k, v in meta.items()
                 if wanted(k) and VERSION_RE.match(v or "")}
    from_doc: dict[str, str] = {}
    for doc in docs:
        for k, v in _doc_versions(doc).items():
            if wanted(k) and k not in from_meta:
                from_doc.setdefault(k, v)

    components = {**from_meta, **from_doc}
    if not components:
        source = SOURCE_NONE
    elif from_meta and from_doc:
        source = SOURCE_MIXED
    elif from_meta:
        source = SOURCE_METADATA
    else:
        source = SOURCE_SUITE_DOC
    return dict(sorted(components.items())), source


def git_commits(repo: str | Path, prev_sha: str, head: str = "HEAD") -> tuple[str, list[dict]]:
    """(HEAD-SHA, Commits seit prev_sha) aus dem Robot-Repo.

    Ist `prev_sha` unbekannt - erster Lauf, force-push, oder der in CI uebliche
    flache Clone -, kommt eine leere Liste zurueck statt eines Abbruchs: ein
    fehlender Commit-Block ist kein Grund, den Nachtlauf zu verlieren.
    (In GitLab CI dafuer `GIT_DEPTH: 0` setzen.)
    """
    repo = str(repo)
    sha = _git(repo, ["rev-parse", head]) or ""
    if not prev_sha or not sha:
        return sha, []
    if _git(repo, ["cat-file", "-e", prev_sha + "^{commit}"]) is None:
        return sha, []
    out = _git(repo, ["log", "--no-merges", "--format=%H%x1f%s%x1f%an",
                      f"{prev_sha}..{sha}"])
    commits = []
    for line in (out or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            # Voller SHA: das Dashboard kuerzt beim Anzeigen, aber `git show`
            # und spaetere Links in die GitLab-Oberflaeche brauchen ihn ganz.
            commits.append({"sha": parts[0], "subject": parts[1], "author": parts[2]})
    return sha, commits


def _git(repo: str, args: list[str]) -> str | None:
    """git im Repo ausfuehren; None bei Fehler (fehlendes Repo, unbekannter SHA)."""
    try:
        p = subprocess.run(["git", "-C", repo] + args, capture_output=True,
                           text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None
