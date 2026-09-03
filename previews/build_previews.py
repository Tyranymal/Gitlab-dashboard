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

from nrd.build import LAYOUT_DIR  # noqa: E402

DATA = HERE / "demo-data.json"

#: Layoutdatei -> Name der Vorschauseite. Die Varianten heissen im Paket nach
#: ihrer Idee, in der Vorschau nach dem Buchstaben, unter dem sie besprochen
#: wurden.
VARIANTEN = {"timeline.html": "a.html", "runbook.html": "b.html"}

for name, out_name in VARIANTEN.items():
    out = build(LAYOUT_DIR / name, DATA, HERE / out_name, LAYOUT_DIR)
    print(f"{out.relative_to(HERE.parent)}  {out.stat().st_size / 1024:.0f} KB")
