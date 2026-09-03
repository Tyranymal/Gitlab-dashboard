"""Kommandozeile: `nrd collect` sammelt einen Lauf ein, `nrd build` baut das
Dashboard, `nrd info` sagt, was in der Historie steht."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import build as build_mod
from .collect import git_commits, parse_output_xml
from .store import Store

DEFAULT_STORE = "data"


def cmd_collect(args) -> int:
    services = [s.strip() for s in args.services.split(",") if s.strip()] \
        if args.services else None
    run = parse_output_xml(args.output_xml, services)
    if args.run_id:
        run.run_id = args.run_id
    if not run.run_id:
        print("Fehler: kein Laufdatum in der output.xml und kein --run-id", file=sys.stderr)
        return 2
    if args.pipeline_id:
        run.pipeline_id = args.pipeline_id

    store = Store(args.store)
    run.prev_sha = store.sha_before(run.run_id)
    if args.repo:
        run.sha, run.commits = git_commits(args.repo, run.prev_sha)

    entry = store.add(run, fail_tag_prefix=args.fail_tag_prefix)
    dropped = store.trim(args.keep) if args.keep else 0
    store.save()

    counts = {c: entry["s"].count(c) for c in "PpfF-"}
    print(f"{run.run_id}: {len(run.results)} Tests "
          f"(P {counts['P']} · p {counts['p']} · f {counts['f']} · F {counts['F']}), "
          f"{len(run.components)} Services aus {run.version_source}, "
          f"{len(run.commits)} Commits")
    if dropped:
        print(f"  {dropped} aeltere Laeufe aus dem Index entfernt (Detaildateien bleiben)")
    print(f"  -> {store.index_path}")
    return 0


def cmd_build(args) -> int:
    data = Path(args.data) if args.data else Path(args.store) / "index.json"
    if not data.exists():
        print(f"Fehler: {data} fehlt - erst `nrd collect` laufen lassen", file=sys.stderr)
        return 2
    if not Path(args.template).exists():
        # Das Layout liegt im Repo, nicht im Paket. Wer nrd woanders hin
        # installiert, muss den Pfad mitgeben.
        print(f"Fehler: Template {args.template} fehlt - Pfad mit --template angeben",
              file=sys.stderr)
        return 2
    out = build_mod.build(args.template, data, args.out, args.assets,
                          runs_dir=Path(args.store) / "runs", messages=args.messages)
    print(f"{out}  {out.stat().st_size / 1024:.0f} KB")
    return 0


def cmd_info(args) -> int:
    store = Store(args.store)
    if not store.runs:
        print(f"{store.index_path}: leer")
        return 0
    first, last = store.runs[0], store.runs[-1]
    print(f"{len(store.runs)} Laeufe · {first['run_id']} bis {last['run_id']}")
    print(f"{len(store.tests)} Tests · {len(store.data['services'])} Services")
    print("letzter Lauf: " + " · ".join(
        f"{c} {last['s'].count(c)}" for c in "PpfF-"))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="nrd", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="output.xml einsammeln")
    c.add_argument("--output-xml", required=True, help="Robot-Framework-output.xml")
    c.add_argument("--store", default=DEFAULT_STORE, help="Verzeichnis der Historie")
    c.add_argument("--repo", default=".", help="Robot-Repo fuer die Commit-Liste ('' = keine)")
    c.add_argument("--run-id", help="Laufdatum YYYY-MM-DD (Vorgabe: Startdatum des Laufs)")
    c.add_argument("--pipeline-id", help="CI-Pipeline, Vorgabe: Suite-Metadata 'Pipeline'")
    c.add_argument("--services", help="Kommaliste: nur diese Metadaten sind Services")
    c.add_argument("--fail-tag-prefix", default="fail:", help="Praefix bekannter Fails")
    c.add_argument("--keep", type=int, default=0, help="nur die juengsten N Laeufe im Index")
    c.set_defaults(func=cmd_collect)

    b = sub.add_parser("build", help="Dashboard bauen")
    b.add_argument("--store", default=DEFAULT_STORE)
    b.add_argument("--data", help="Datendatei (Vorgabe: <store>/index.json)")
    b.add_argument("--template", default=str(build_mod.DEFAULT_TEMPLATE))
    b.add_argument("--assets", default=str(build_mod.DEFAULT_ASSETS))
    b.add_argument("--out", default="public/index.html")
    b.add_argument("--messages", type=int, default=5,
                   help="Fehlermeldungen der juengsten N Naechte einbetten (0 = keine)")
    b.set_defaults(func=cmd_build)

    i = sub.add_parser("info", help="Historie zusammenfassen")
    i.add_argument("--store", default=DEFAULT_STORE)
    i.set_defaults(func=cmd_info)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
