"""Setzt aus Layout-Template, gemeinsamem CSS/JS und der Historie eine
eigenstaendige HTML-Datei zusammen.

Die Daten werden eingebettet, nicht nachgeladen. Das haelt die Datei per
Doppelklick lauffaehig und spart in der GitLab-Instanz einen zweiten Request -
und `index.json` ist klein genug dafuer: rund 1 KB je Nacht bei 200 Tests,
also etwa 350 KB fuer drei Jahre. Wird es deutlich mehr, ist der Umstieg auf
`fetch()` faellig; bis dahin waere er nur zusaetzliche Mechanik.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TOKENS = {"css": "/*__CSS__*/", "core": "/*__CORE__*/", "data": "/*__DATA__*/"}

#: Layout und gemeinsame Assets liegen im Paket, nicht daneben: wer das
#: Dashboard in sein Robot-Repo holt, kopiert damit ein Verzeichnis - nrd/ -
#: und hat Collector, Historie, Build und Layout beisammen.
LAYOUT_DIR = Path(__file__).resolve().parent / "layout"
DEFAULT_TEMPLATE = LAYOUT_DIR / "timeline.html"
DEFAULT_ASSETS = LAYOUT_DIR


def render(template: str | Path, data_json: str, assets: str | Path = DEFAULT_ASSETS) -> str:
    """Template + Assets + Daten -> fertiges HTML."""
    assets = Path(assets)
    html = Path(template).read_text(encoding="utf-8")
    values = {
        "css": (assets / "core.css").read_text(encoding="utf-8"),
        "core": (assets / "core.js").read_text(encoding="utf-8"),
        "data": data_json,
    }
    for key, token in TOKENS.items():
        if token not in html:
            raise ValueError(f"{Path(template).name}: Platzhalter {token} fehlt")
        html = html.replace(token, values[key])
    return html


#: Fehlermeldungen sind Freitext und koennen ganze Stacktraces sein. Im
#: Dashboard interessiert die erste Zeile - der Rest steht in der Detaildatei.
MESSAGE_MAX = 400


def data_with_messages(index_path: str | Path, runs_dir: str | Path,
                       keep: int) -> str:
    """`index.json` als Text, angereichert um die Fehlermeldungen der juengsten
    `keep` Naechte.

    Die Meldungen liegen in den Detaildateien, nicht im Index - sonst waere der
    Index um ein Vielfaches groesser, obwohl morgens nur die letzten Naechte
    aufgeklappt werden. Sie werden hier beim Bauen eingesetzt, damit die Seite
    ohne zweiten Request auskommt und per Doppelklick lauffaehig bleibt.
    """
    data = json.loads(Path(index_path).read_text(encoding="utf-8"))
    if keep <= 0:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    pos = {(t["suite"], t["name"]): i for i, t in enumerate(data.get("tests", []))}
    runs_dir = Path(runs_dir)
    for run in data.get("runs", [])[-keep:]:
        detail_path = runs_dir / f"{run['run_id']}.json"
        if not detail_path.exists():
            continue
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        msgs = {}
        for t in detail.get("tests", []):
            i = pos.get((t.get("suite"), t.get("name")))
            # Nur zu dem, was rot ist: bei bestandenen Tests steht in der
            # Meldung nichts, was jemanden interessiert.
            if i is None or run["s"][i] not in "fF" or not t.get("message"):
                continue
            text = re.sub(r"\s+", " ", t["message"]).strip()
            msgs[str(i)] = text[:MESSAGE_MAX] + ("…" if len(text) > MESSAGE_MAX else "")
        if msgs:
            run["msgs"] = msgs
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build(template: str | Path, data_path: str | Path, out: str | Path,
          assets: str | Path = DEFAULT_ASSETS, runs_dir: str | Path | None = None,
          messages: int = 0) -> Path:
    """Dashboard aus einer Datendatei bauen und schreiben."""
    data_json = (data_with_messages(data_path, runs_dir, messages)
                 if runs_dir and messages
                 else Path(data_path).read_text(encoding="utf-8"))
    html = render(template, data_json, assets)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
