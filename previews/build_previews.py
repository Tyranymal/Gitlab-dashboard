#!/usr/bin/env python3
"""Baut die Vorschauseiten aus dem synthetischen Datensatz.

Dasselbe Zusammensetzen wie `nrd build`, nur mit `demo-data.json` statt einer
echten Historie - deshalb ruft das Skript den Builder des Pakets auf, statt die
Platzhalterlogik ein zweites Mal zu fuehren.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from nrd.build import build  # noqa: E402

DATA = HERE / "demo-data.json"

for tpl in sorted((HERE / "templates").glob("*.html")):
    out = build(tpl, DATA, HERE / tpl.name, HERE / "shared")
    print(f"{out.relative_to(HERE.parent)}  {out.stat().st_size / 1024:.0f} KB")
