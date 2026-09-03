"""Historie der Nachtlaeufe: `index.json` fuer die Uebersicht, `runs/*.json`
fuer die Details eines einzelnen Laufs.

Die Aufteilung ist keine Optimierung um ihrer selbst willen. `index.json` ist
das, was das Dashboard komplett laedt - es muss klein bleiben und darf keine
Fehlermeldungen und Keyword-Namen mitschleppen. Die Detaildateien sind das
Archiv: einmal geschrieben, nie wieder angefasst, aber vorhanden, wenn jemand
in einem halben Jahr wissen will, woran ein Test damals gescheitert ist.

Zwei Eigenschaften, auf denen alles andere aufbaut:

* Die Testliste ist **append-only**. Ein Test behaelt seine Position, solange
  es die Historie gibt; ein entfallener Test bekommt in neuen Laeufen `-`,
  seine Spalte wandert nicht. Sonst wuerde jeder umbenannte Test die gesamte
  Historie verschieben.
* Ein erneutes Einsammeln desselben Laufs **ersetzt** ihn. `nrd collect` darf
  wiederholbar sein, ohne die Historie zu verdoppeln.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .model import ABSENT, LEGEND, SCHEMA, Run, status_code

INDEX_NAME = "index.json"
RUNS_DIR = "runs"


class Store:
    """Dateibasierte Historie unter einem Verzeichnis."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.index_path = self.path / INDEX_NAME
        self.runs_dir = self.path / RUNS_DIR
        self.data = self._load()

    # ------------------------------------------------------------------ IO
    def _load(self) -> dict:
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            data.setdefault("services", [])
            data.setdefault("tests", [])
            data.setdefault("runs", [])
            return data
        return {"schema": SCHEMA, "generated": "", "services": [],
                "tests": [], "runs": [], "legend": LEGEND}

    def save(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        self.data["schema"] = SCHEMA
        self.data["legend"] = LEGEND
        self.data["generated"] = datetime.now(timezone.utc).replace(
            microsecond=0).isoformat()
        # Kompakt: die Datei geht als Ganzes ins Dashboard.
        self.index_path.write_text(
            json.dumps(self.data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        return self.index_path

    # --------------------------------------------------------------- Lesen
    @property
    def runs(self) -> list[dict]:
        return self.data["runs"]

    @property
    def tests(self) -> list[dict]:
        return self.data["tests"]

    def last_run(self) -> dict | None:
        return self.runs[-1] if self.runs else None

    def run(self, run_id: str) -> dict | None:
        return next((r for r in self.runs if r["run_id"] == run_id), None)

    def sha_before(self, run_id: str) -> str:
        """SHA des Laufs, der zeitlich vor `run_id` liegt - die Vergleichsbasis."""
        prev = [r for r in self.runs if r["run_id"] < run_id]
        return prev[-1].get("sha", "") if prev else ""

    # -------------------------------------------------------------- Ablegen
    def add(self, run: Run, fail_tag_prefix: str = "fail:") -> dict:
        """Lauf einsortieren (oder ersetzen) und die Detaildatei schreiben."""
        index_of = self._merge_tests(run)
        codes = [ABSENT] * len(self.tests)
        for r in run.results:
            codes[index_of[r.key]] = status_code(r.status, r.tags, fail_tag_prefix)

        for name in run.components:
            if name not in self.data["services"]:
                self.data["services"].append(name)

        entry = {
            "run_id": run.run_id,
            "started_at": run.started_at,
            "elapsed_s": run.elapsed_s,
            "components": run.components,
            "version_source": run.version_source,
            "pipeline_id": run.pipeline_id,
            "sha": run.sha,
            "prev_sha": run.prev_sha,
            "commits": run.commits,
            "s": "".join(codes),
        }
        self.runs[:] = [r for r in self.runs if r["run_id"] != run.run_id]
        self.runs.append(entry)
        self.runs.sort(key=lambda r: r["run_id"])
        self._pad_runs()
        self._relink_shas()
        self._write_detail(run)
        return entry

    def _merge_tests(self, run: Run) -> dict[tuple[str, str], int]:
        """Neue Tests hinten anhaengen, bestehende Positionen behalten."""
        index_of = {(t["suite"], t["name"]): i for i, t in enumerate(self.tests)}
        for r in run.results:
            if r.key not in index_of:
                index_of[r.key] = len(self.tests)
                self.tests.append({"suite": r.suite, "name": r.name})
        return index_of

    def _pad_runs(self) -> None:
        """Alle Laufstrings auf die aktuelle Testzahl bringen.

        Aeltere Laeufe kannten spaeter hinzugekommene Tests nicht - deren
        Zeichen ist `-`, nicht etwa pass.
        """
        n = len(self.tests)
        for r in self.runs:
            if len(r["s"]) < n:
                r["s"] = r["s"] + ABSENT * (n - len(r["s"]))

    def _relink_shas(self) -> None:
        """prev_sha jedes Laufs auf den tatsaechlichen Vorlauf setzen."""
        prev = ""
        for r in self.runs:
            r["prev_sha"] = prev
            prev = r.get("sha", "") or prev

    def _write_detail(self, run: Run) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        out = self.runs_dir / f"{run.run_id}.json"
        out.write_text(json.dumps({
            "schema": SCHEMA,
            "run_id": run.run_id,
            "started_at": run.started_at,
            "elapsed_s": run.elapsed_s,
            "generator": run.generator,
            "components": run.components,
            "version_source": run.version_source,
            "pipeline_id": run.pipeline_id,
            "sha": run.sha,
            "prev_sha": run.prev_sha,
            "commits": run.commits,
            "tests": [{"suite": r.suite, "name": r.name, "status": r.status,
                       "tags": r.tags, "message": r.message,
                       "elapsed_s": round(r.elapsed_s, 3)} for r in run.results],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        return out

    def trim(self, keep: int) -> int:
        """Nur die juengsten `keep` Laeufe im Index lassen.

        Die Detaildateien bleiben liegen - der Index ist das Anzeigefenster,
        `runs/` das Archiv. Zurueck kommt die Zahl der entfernten Laeufe.
        """
        if keep <= 0 or len(self.runs) <= keep:
            return 0
        dropped = len(self.runs) - keep
        self.runs[:] = self.runs[-keep:]
        self._relink_shas()
        self.runs[0]["prev_sha"] = ""
        return dropped
