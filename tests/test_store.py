"""Historie: stabile Testpositionen, ersetzbare Laeufe, verkettete SHAs."""
import json

import pytest

from nrd.model import ABSENT, Run, CaseResult
from nrd.store import Store


def mkrun(run_id, tests, sha="", components=None):
    """tests: {(suite, name): status}"""
    return Run(run_id=run_id, started_at=run_id + "T01:00:00", elapsed_s=3600, sha=sha,
               components=components or {"svc": "1.0.0"}, version_source="metadata",
               results=[CaseResult(suite=s, name=n, status=st)
                        for (s, n), st in tests.items()])


def test_erster_lauf(tmp_path):
    store = Store(tmp_path)
    entry = store.add(mkrun("2026-01-01", {("S", "a"): "PASS", ("S", "b"): "FAIL"}))
    assert entry["s"] == "PF"
    assert store.data["services"] == ["svc"]


def test_neue_tests_haengen_hinten_an_und_fuellen_alte_laeufe(tmp_path):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS"}))
    store.add(mkrun("2026-01-02", {("S", "a"): "PASS", ("S", "neu"): "FAIL"}))
    assert [t["name"] for t in store.tests] == ["a", "neu"]
    # Der alte Lauf kannte "neu" nicht - das ist kein pass, sondern nicht im Lauf.
    assert store.runs[0]["s"] == "P" + ABSENT
    assert store.runs[1]["s"] == "PF"


def test_entfallener_test_behaelt_seine_position(tmp_path):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS", ("S", "weg"): "PASS"}))
    store.add(mkrun("2026-01-02", {("S", "a"): "FAIL"}))
    assert [t["name"] for t in store.tests] == ["a", "weg"]
    assert store.runs[1]["s"] == "F" + ABSENT


def test_erneutes_einsammeln_ersetzt(tmp_path):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "FAIL"}))
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS"}))
    assert len(store.runs) == 1 and store.runs[0]["s"] == "P"


def test_laeufe_bleiben_chronologisch(tmp_path):
    store = Store(tmp_path)
    for d in ("2026-01-03", "2026-01-01", "2026-01-02"):
        store.add(mkrun(d, {("S", "a"): "PASS"}))
    assert [r["run_id"] for r in store.runs] == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_prev_sha_zeigt_auf_den_vorlauf(tmp_path):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS"}, sha="aaa"))
    store.add(mkrun("2026-01-03", {("S", "a"): "PASS"}, sha="ccc"))
    # Nachtraeglich eingefuegter Lauf dazwischen: die Kette muss sich neu ordnen,
    # sonst vergleicht der 3. gegen den 1. und die Commit-Liste stimmt nicht mehr.
    store.add(mkrun("2026-01-02", {("S", "a"): "PASS"}, sha="bbb"))
    assert [r["run_id"] for r in store.runs] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert [r["prev_sha"] for r in store.runs] == ["", "aaa", "bbb"]


def test_sha_before(tmp_path):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS"}, sha="aaa"))
    assert store.sha_before("2026-01-02") == "aaa"
    assert store.sha_before("2026-01-01") == ""


def test_detaildatei_haelt_meldung_und_tags(tmp_path):
    store = Store(tmp_path)
    run = mkrun("2026-01-01", {("S", "a"): "FAIL"})
    run.results[0].message = "Timeout nach 30s"
    run.results[0].tags = ["fail:DEV-1"]
    store.add(run)
    detail = json.loads((tmp_path / "runs" / "2026-01-01.json").read_text())
    assert detail["tests"][0]["message"] == "Timeout nach 30s"
    assert detail["tests"][0]["tags"] == ["fail:DEV-1"]


def test_speichern_und_wieder_laden(tmp_path):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS"}))
    store.save()
    wieder = Store(tmp_path)
    assert len(wieder.runs) == 1 and wieder.data["generated"]
    assert wieder.data["legend"]["-"] == "nicht im Lauf"


def test_trim_behaelt_die_juengsten(tmp_path):
    store = Store(tmp_path)
    for d in range(1, 6):
        store.add(mkrun(f"2026-01-0{d}", {("S", "a"): "PASS"}, sha=f"s{d}"))
    assert store.trim(3) == 2
    assert [r["run_id"] for r in store.runs] == ["2026-01-03", "2026-01-04", "2026-01-05"]
    assert store.runs[0]["prev_sha"] == ""      # kein Verweis auf Gekapptes
    # Die Detaildateien bleiben als Archiv liegen.
    assert (tmp_path / "runs" / "2026-01-01.json").exists()


@pytest.mark.parametrize("keep", [0, 9])
def test_trim_ohne_wirkung(tmp_path, keep):
    store = Store(tmp_path)
    store.add(mkrun("2026-01-01", {("S", "a"): "PASS"}))
    assert store.trim(keep) == 0 and len(store.runs) == 1
