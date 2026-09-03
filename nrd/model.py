"""Datenmodell und Statuscodes des Nachtlauf-Dashboards.

Ein Lauf wird nicht als Liste von Testobjekten gespeichert, sondern als ein
String mit einem Zeichen je Test. Bei 214 Tests und einem Jahr Historie ist das
der Unterschied zwischen ~80 MB und ~80 KB - und der Grund, warum das Dashboard
seine Daten inline mitbringen kann.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA = 1

PASS = "P"          # bestanden
PASS_TAGGED = "p"   # bestanden, obwohl ein fail:-Tag gesetzt ist (Tag-Kandidat)
FAIL_KNOWN = "f"    # fehlgeschlagen, fail:-Tag gesetzt - bekannt
FAIL_NEW = "F"      # fehlgeschlagen ohne Tag - das, was morgens interessiert
ABSENT = "-"        # im Lauf nicht vorhanden (auch: uebersprungen)

LEGEND = {
    PASS: "pass",
    PASS_TAGGED: "pass, fail-Tag gesetzt",
    FAIL_KNOWN: "fail, bekannt (fail-Tag)",
    FAIL_NEW: "fail, neu",
    ABSENT: "nicht im Lauf",
}

#: Quelle der Service-Versionen, wie sie im Dashboard benannt wird.
SOURCE_METADATA = "metadata"
SOURCE_SUITE_DOC = "suite_doc"
SOURCE_MIXED = "mixed"
SOURCE_NONE = "none"


def status_code(status: str, tags, fail_tag_prefix: str = "fail:") -> str:
    """Robot-Status + Tags -> ein Zeichen.

    SKIP zaehlt als "nicht im Lauf": ein uebersprungener Test hat kein
    Ergebnis, und ihn als pass zu zaehlen faerbt die Bilanz gruen.
    """
    tagged = any(t.lower().startswith(fail_tag_prefix.lower()) for t in tags)
    if status == "PASS":
        return PASS_TAGGED if tagged else PASS
    if status == "FAIL":
        return FAIL_KNOWN if tagged else FAIL_NEW
    return ABSENT


@dataclass
class CaseResult:
    """Ein Testergebnis eines Laufs, wie es aus der output.xml faellt."""
    suite: str
    name: str
    status: str                      # PASS | FAIL | SKIP | NOT RUN
    tags: list[str] = field(default_factory=list)
    message: str = ""
    elapsed_s: float = 0.0

    @property
    def key(self) -> tuple[str, str]:
        return (self.suite, self.name)


@dataclass
class Run:
    """Ein Nachtlauf: Metadaten, Versionsstand, Ergebnisse."""
    run_id: str                      # YYYY-MM-DD, Datum des Laufbeginns
    started_at: str
    elapsed_s: int
    components: dict[str, str] = field(default_factory=dict)
    version_source: str = SOURCE_NONE
    pipeline_id: str = ""
    sha: str = ""
    prev_sha: str = ""
    commits: list[dict] = field(default_factory=list)
    results: list[CaseResult] = field(default_factory=list)
    generator: str = ""
