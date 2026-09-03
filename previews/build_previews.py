#!/usr/bin/env python3
"""Baut die drei Vorschauseiten: Template + gemeinsame CSS/JS + Demo-Daten
werden zu je einer eigenstaendigen HTML-Datei zusammengesetzt.

Bewusst ohne externe Assets: die fertige Datei laeuft per Doppelklick, ohne
Server und ohne Internet - dieselbe Eigenschaft, die sie spaeter in einer
abgeschotteten GitLab-Instanz braucht.
"""
from pathlib import Path

HERE = Path(__file__).parent
CSS = (HERE / "shared" / "core.css").read_text(encoding="utf-8")
JS = (HERE / "shared" / "core.js").read_text(encoding="utf-8")
DATA = (HERE / "demo-data.json").read_text(encoding="utf-8")

for tpl in sorted((HERE / "templates").glob("*.html")):
    html = tpl.read_text(encoding="utf-8")
    for token, value in (("/*__CSS__*/", CSS), ("/*__CORE__*/", JS), ("/*__DATA__*/", DATA)):
        if token not in html:
            raise SystemExit(f"{tpl.name}: Platzhalter {token} fehlt")
        html = html.replace(token, value)
    out = HERE / tpl.name
    out.write_text(html, encoding="utf-8")
    print(f"{out.relative_to(HERE.parent)}  {out.stat().st_size / 1024:.0f} KB")
