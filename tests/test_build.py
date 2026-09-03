"""Build und die Kette collect -> store -> build am Stueck."""
import json
from pathlib import Path

import pytest

from nrd import build as build_mod
from nrd.cli import main
from nrd.collect import parse_output_xml
from nrd.store import Store

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def assets(tmp_path):
    d = tmp_path / "shared"
    d.mkdir()
    (d / "core.css").write_text("body{color:red}")
    (d / "core.js").write_text("const RUNS = DATA.runs;")
    return d


def test_render_setzt_alle_platzhalter(tmp_path, assets):
    tpl = tmp_path / "t.html"
    tpl.write_text("<style>/*__CSS__*/</style><script>const DATA=/*__DATA__*/;"
                   "/*__CORE__*/</script>")
    html = build_mod.render(tpl, '{"runs":[]}', assets)
    assert "body{color:red}" in html and 'const DATA={"runs":[]};' in html
    assert "/*__" not in html


def test_fehlender_platzhalter_faellt_auf(tmp_path, assets):
    tpl = tmp_path / "t.html"
    tpl.write_text("<style>/*__CSS__*/</style>")     # __DATA__ und __CORE__ fehlen
    with pytest.raises(ValueError, match="__CORE__|__DATA__"):
        build_mod.render(tpl, "{}", assets)


def test_kette_von_der_output_xml_bis_zur_html(tmp_path):
    """Ein Lauf einsammeln, ablegen, das echte Layout damit bauen."""
    store = Store(tmp_path / "data")
    run = parse_output_xml(FIXTURES / "rf7_output.xml")
    run.sha = "a" * 40
    store.add(run)
    store.save()

    out = build_mod.build(build_mod.DEFAULT_TEMPLATE, store.index_path,
                          tmp_path / "public" / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "/*__" not in html                        # kein Platzhalter blieb stehen
    assert "2026-09-03" in html                      # der Lauf steckt drin
    assert "Check Baud Rate Switch" in html
    assert "ingest-service" in html
    assert out.stat().st_size > 40_000               # Layout und Kern sind dabei


def test_cli_collect_build_info(tmp_path, capsys):
    store = tmp_path / "data"
    assert main(["collect", "--output-xml", str(FIXTURES / "rf7_output.xml"),
                 "--store", str(store), "--repo", ""]) == 0
    assert main(["info", "--store", str(store)]) == 0
    assert main(["build", "--store", str(store),
                 "--out", str(tmp_path / "public" / "index.html")]) == 0
    ausgabe = capsys.readouterr().out
    assert "4 Tests" in ausgabe and "1 Laeufe" in ausgabe
    assert (tmp_path / "public" / "index.html").exists()

    index = json.loads((store / "index.json").read_text())
    assert index["runs"][0]["s"] == "PfF-"          # pass · bekannt · neu · uebersprungen


def test_build_ohne_daten_meldet_sich(tmp_path, capsys):
    assert main(["build", "--store", str(tmp_path / "leer")]) == 2
    assert "erst `nrd collect`" in capsys.readouterr().err
