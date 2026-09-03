"""Setzt aus Layout-Template, gemeinsamem CSS/JS und der Historie eine
eigenstaendige HTML-Datei zusammen.

Die Daten werden eingebettet, nicht nachgeladen. Das haelt die Datei per
Doppelklick lauffaehig und spart in der GitLab-Instanz einen zweiten Request -
und `index.json` ist klein genug dafuer: rund 1 KB je Nacht bei 200 Tests,
also etwa 350 KB fuer drei Jahre. Wird es deutlich mehr, ist der Umstieg auf
`fetch()` faellig; bis dahin waere er nur zusaetzliche Mechanik.
"""
from __future__ import annotations

from pathlib import Path

TOKENS = {"css": "/*__CSS__*/", "core": "/*__CORE__*/", "data": "/*__DATA__*/"}

#: Layout und gemeinsame Assets liegen (historisch) unter previews/.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / "previews" / "templates" / "a.html"
DEFAULT_ASSETS = REPO_ROOT / "previews" / "shared"


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


def build(template: str | Path, data_path: str | Path, out: str | Path,
          assets: str | Path = DEFAULT_ASSETS) -> Path:
    """Dashboard aus einer Datendatei bauen und schreiben."""
    html = render(template, Path(data_path).read_text(encoding="utf-8"), assets)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
