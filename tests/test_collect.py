"""Der Collector gegen beide output.xml-Formate."""
import subprocess
from pathlib import Path

import pytest

from nrd.collect import git_commits, parse_output_xml, resolve_versions
from nrd.model import ABSENT, FAIL_KNOWN, FAIL_NEW, PASS, PASS_TAGGED, status_code

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(params=["rf7_output.xml", "rf6_output.xml"])
def run(request):
    """Derselbe Lauf, einmal im Robot-7- und einmal im Robot-6-Format."""
    return parse_output_xml(FIXTURES / request.param)


def test_tests_werden_vollstaendig_gelesen(run):
    assert [t.name for t in run.results] == [
        "Verify Cold Start", "Check Baud Rate Switch",
        "Report Watchdog Trip", "Detect Sensor Timeout"]


def test_suitepfad_ohne_wurzelsuite(run):
    # "Nightly" ist der Lauf selbst und steht sonst vor jedem Suitenamen.
    assert {t.suite for t in run.results} == {"Device.Connection"}


def test_tags_und_meldung(run):
    baud = next(t for t in run.results if t.name == "Check Baud Rate Switch")
    assert "fail:DEV-1047" in baud.tags
    assert baud.message == "Firmware antwortet nicht"


def test_laufzeit_kommt_von_der_wurzelsuite(run):
    # <statistics> enthaelt selbst ein <suite>-Element; wird das mitgezaehlt,
    # sind Startzeit und Laufzeit am Ende leer.
    assert run.started_at.startswith("2026-09-03T19:23:40")
    assert run.run_id == "2026-09-03"


def test_pipeline_aus_metadata(run):
    assert run.pipeline_id == "48623"


def test_versionen_aus_metadata_und_doku(run):
    # Metadata (ingest, calibration) und Suite-Doku (api-gateway, auth-service)
    assert run.components == {"api-gateway": "3.5.1", "auth-service": "2.15.0",
                              "calibration-svc": "0.33.1", "ingest-service": "7.3.0"}
    assert run.version_source == "mixed"


def test_services_filter():
    run = parse_output_xml(FIXTURES / "rf7_output.xml", ["ingest-service"])
    assert run.components == {"ingest-service": "7.3.0"}
    assert run.version_source == "metadata"


def test_leere_output_xml(tmp_path):
    p = tmp_path / "leer.xml"
    p.write_text('<?xml version="1.0"?><robot><suite id="s1" name="X">'
                 '<status status="PASS" start="2026-01-01T00:00:00" elapsed="1"/>'
                 '</suite></robot>')
    with pytest.raises(ValueError):
        parse_output_xml(p)


# --------------------------------------------------------------- Statuscodes
@pytest.mark.parametrize("status,tags,erwartet", [
    ("PASS", [], PASS),
    ("PASS", ["fail:DEV-1"], PASS_TAGGED),
    ("FAIL", ["fail:DEV-1"], FAIL_KNOWN),
    ("FAIL", ["smoke"], FAIL_NEW),
    ("FAIL", ["FAIL:DEV-1"], FAIL_KNOWN),      # Tags sind nicht case-sensitiv
    ("SKIP", [], ABSENT),                       # uebersprungen ist kein Ergebnis
    ("NOT RUN", [], ABSENT),
])
def test_status_code(status, tags, erwartet):
    assert status_code(status, tags) == erwartet


# ------------------------------------------------------------- Versionsquelle
def test_pipelinenummer_ist_keine_version():
    comps, source = resolve_versions({"Pipeline": "48623", "svc": "1.2.0"}, [])
    assert comps == {"svc": "1.2.0"} and source == "metadata"


def test_doku_fuellt_nur_luecken():
    comps, source = resolve_versions({"svc": "2.0.0"}, ["svc: 1.0.0\nandere: 3.1.0"])
    assert comps == {"svc": "2.0.0", "andere": "3.1.0"}
    assert source == "mixed"


def test_ohne_angaben():
    comps, source = resolve_versions({"Autor": "t.ruf"}, ["kein Treffer"])
    assert comps == {} and source == "none"


# -------------------------------------------------------------------- Commits
def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name in ("a", "b"):
        subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "--allow-empty",
                        "-m", f"Commit {name}", "--author=t.ruf <t@x>"],
                       env={"GIT_COMMITTER_NAME": "t.ruf", "GIT_COMMITTER_EMAIL": "t@x",
                            "PATH": "/usr/bin:/bin"}, check=True)
    return tmp_path


def test_commits_seit_vorlauf(tmp_path):
    repo = _repo(tmp_path)
    first = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD~1"],
                           capture_output=True, text=True).stdout.strip()
    sha, commits = git_commits(repo, first)
    assert len(sha) == 40
    assert [c["subject"] for c in commits] == ["Commit b"]
    assert commits[0]["author"] == "t.ruf"
    assert len(commits[0]["sha"]) == 40


def test_unbekannter_vorlauf_ist_kein_abbruch(tmp_path):
    # Flacher CI-Clone oder force-push: lieber keine Commit-Liste als kein Lauf.
    repo = _repo(tmp_path)
    sha, commits = git_commits(repo, "0" * 40)
    assert sha and commits == []


def test_ohne_repo_bleibt_leer(tmp_path):
    sha, commits = git_commits(tmp_path / "gibtsnicht", "abc")
    assert sha == "" and commits == []
