# Nachtlauf-Dashboard

Aus den nächtlichen Robot-Framework-Läufen eines Microservice-Verbunds wird eine
Seite, die morgens die eine Frage beantwortet: *Was ist heute Nacht kaputtgegangen,
und woran hing es?*

Das Werkzeug heißt `nrd`, besteht aus drei Schritten und hat **keine
Laufzeit-Abhängigkeiten** – die `output.xml` wird mit der Standardbibliothek
gelesen. In einer abgeschotteten Instanz gibt es damit nichts zu beschaffen
außer Python selbst.

```
output.xml ──nrd collect──► data/index.json ──nrd build──► public/index.html
                            data/runs/*.json
```

## Stand

| Teil | Stand |
|---|---|
| Layout (drei Varianten, Variante A gewählt) | fertig, siehe [`previews/`](previews/README.md) |
| Collector `output.xml` → Lauf | fertig, getestet gegen Robot 6- und 7-Format |
| Historie (`index.json` + `runs/*.json`) | fertig |
| Build (Daten + Layout → eine HTML) | fertig |
| GitLab-CI-Pipeline und Pages | geschrieben, **nicht** auf einer echten Instanz gelaufen |
| Gegen eine echte Nachtlauf-Suite gelaufen | nein – siehe *Was noch offen ist* |

## Schnellstart

```bash
python3 -m nrd collect --output-xml rf-out/output.xml --store data --repo .
python3 -m nrd build   --store data --out public/index.html
python3 -m nrd info    --store data
```

`nrd collect` ist wiederholbar: dieselbe Nacht noch einmal einsammeln ersetzt
den Lauf, statt ihn zu verdoppeln.

Nützliche Schalter: `--run-id 2026-09-03` überschreibt das aus der `output.xml`
gelesene Datum, `--services a,b,c` beschränkt, welche Metadaten als Service
gelten, `--keep 400` hält den Index auf die jüngsten N Nächte begrenzt, und
`--fail-tag-prefix` ändert die Konvention für bekannte Fails.

## Konventionen in der Suite

**Service-Versionen** kommen aus den Suite-Metadaten – ausdrücklich gesetzt und
damit belastbar:

```robot
*** Settings ***
Metadata    ingest-service     7.3.0
Metadata    calibration-svc    0.33.1
```

Was dort nicht steht, sucht der Collector in der **Suite-Dokumentation**
(`[Documentation]` bzw. `Documentation` in den Settings, im XML das `<doc>` einer
Suite – auf jeder Ebene, nicht nur der äußersten). Erkannt wird eine Zeile, die
für sich allein aus Name, Trennzeichen und Version besteht:

```
^\s*([A-Za-z][\w.\-]*)\s*[:=]\s*(v?\d+\.\d+[\w.\-+]*)\s*$
```

Also `ingest-service: 7.3.0` oder `api-gateway = v3.5.1`, jeweils allein auf einer
Zeile; das führende `v` fällt weg. Nicht erkannt wird alles, was noch Fließtext
daneben hat (`läuft gegen ingest-service 7.3.0`), und alles ohne Punkt in der
Zahl – deshalb rutscht weder `Pipeline: 48623` noch `siehe DEV-1047` durch. Aus
den Metadaten zählt nach derselben Punkt-Regel jeder Eintrag, dessen Wert wie
eine Version aussieht; mit `--services a,b,c` lässt sich das auf eine feste Liste
einengen.

Metadaten gewinnen, die Doku füllt nur, was dort fehlt. Woher es kam, steht als
`version_source` am Lauf (`metadata`, `suite_doc`, `mixed`, `none`) – damit
niemand eine aus der Doku geschätzte Version für einen Build-Fakt hält.

**Bekannte Fails** tragen einen Tag mit dem Präfix `fail:`, üblicherweise mit
Ticketnummer: `[Tags]    fail:DEV-1047`. Daraus entstehen zwei der vier
Statusfarben – ein getaggter Fail ist bekannt, ein ungetaggter ist die Arbeit
für heute. Läuft ein getaggter Test wieder durch, taucht er als Tag-Kandidat auf.

**Übersprungene Tests** (`SKIP`) zählen als *nicht im Lauf*, nicht als bestanden:
ein übersprungener Test hat kein Ergebnis, und ihn grün zu zählen färbt die
Bilanz.

## Das Datenformat

`index.json` ist das, was das Dashboard komplett lädt, und bleibt deshalb klein:
eine Testliste und je Lauf **ein String mit einem Zeichen pro Test** –
`P` pass · `p` pass trotz `fail:`-Tag · `f` bekannter Fail · `F` neuer Fail ·
`-` nicht im Lauf. Bei 214 Tests sind das rund 1 KB je Nacht, also etwa 350 KB
für drei Jahre; deshalb bettet der Build die Daten ein, statt sie nachzuladen.

Zwei Eigenschaften, auf denen der Rest aufbaut:

* Die Testliste ist **append-only**. Ein Test behält seine Position, solange es
  die Historie gibt; ein entfallener Test bekommt `-`, seine Spalte wandert
  nicht. Sonst verschöbe jeder umbenannte Test die gesamte Vergangenheit.
* Verglichen wird immer gegen den vorherigen **Lauf**, nie gegen „gestern". Fällt
  eine Nacht aus, verschiebt sich der Vergleich mit – und das Dashboard schreibt
  dazu, dass der Vorlauf nicht der Vortag war.

`runs/<datum>.json` ist das Archiv: pro Test Status, Tags, Fehlermeldung und
Dauer. Beim Bauen setzt `nrd build --messages N` (Vorgabe 5) die Fehlermeldungen
der jüngsten N Nächte in die Seite ein – nur zu den roten Tests, auf 400 Zeichen
gekürzt, Umbrüche zusammengezogen. Im Dashboard steht die Meldung einzeilig unter
dem Test und klappt per Klick auf. Ältere Nächte tragen keine Meldung; dort ist
die Detaildatei die Quelle. Das hält den Index klein und die Seite ohne zweiten
Request lauffähig.

Die Status-Card hat dafür zwei Sichten: *Wechsel* (was sich gegenüber dem Vorlauf
geändert hat) und *alle Fehlschläge* (was in dieser Nacht rot ist, neue zuerst).
Ein Test, der die dritte Nacht in Folge fällt, steht in keiner Wechselliste –
seine Meldung wäre sonst nirgends zu sehen.

## Was gehört in welches Repo

**Alles in das Repo mit der Robot-Suite.** Der Collector holt die Commit-Liste
aus genau diesem Repo (`--repo .`), und die Pipeline, die die Suite fährt, ist
dieselbe, die einsammelt und veröffentlicht. Ein getrenntes Werkzeug-Repo hieße,
das eine ins andere zu klonen, ohne dass etwas gewonnen wäre.

Zu kopieren sind zwei Dinge:

```
nrd/               # Collector, Historie, Build und Layout - ein Verzeichnis
.gitlab-ci.yml     # die Pipeline
```

Das Layout liegt bewusst **im** Paket (`nrd/layout/`), damit es bei genau einem
Verzeichnis bleibt. Wer das Aussehen ändern will, bearbeitet
`nrd/layout/timeline.html`; `core.css` und `core.js` sind dieselben Bausteine,
aus denen auch die Vorschauen entstehen.

Optional dazu: `tests/` und `pyproject.toml`. Ohne `tests/` muss der `pytest`-Job
aus der `.gitlab-ci.yml` gestrichen werden, sonst schlägt er fehl. `previews/`
wird nicht gebraucht – das ist die Entwurfsstrecke mit erfundenen Daten.

Danach im Suite-Repo:

1. In `.gitlab-ci.yml` den Pfad der Suite anpassen (dort steht `suites/`).
2. `Metadata`-Zeilen für die Service-Versionen in die Suite setzen (siehe oben).
3. Projekt-Access-Token mit `write_repository` anlegen und als maskierte,
   geschützte CI-Variable `NRD_STORE_TOKEN` hinterlegen.
4. Unter CI/CD → Schedules einen nächtlichen Zeitplan anlegen. Der Branch
   `nightly-data` entsteht beim ersten Lauf von selbst.
5. Zum Ausprobieren den Schedule einmal von Hand starten (▶ in der
   Schedule-Liste) – der `nachtlauf`-Job läuft nur in geplanten Pipelines.

Nach dem ersten Durchlauf liegt die Seite unter der Pages-URL des Projekts, die
Historie auf `nightly-data`, das Rohergebnis als Job-Artefakt.

## In GitLab

`.gitlab-ci.yml` enthält drei Jobs: `pytest` für dieses Repo, `nachtlauf` für
die geplante Pipeline und `pages` zum Veröffentlichen. Voraussetzungen:

* **GitLab Pages muss auf der Instanz aktiviert sein.** Die HTML einfach ins Repo
  zu legen reicht nicht – der Repo-Viewer zeigt sie als Quelltext, und die
  `raw`-Endpunkte liefern `text/plain` aus. Ohne Pages bleibt nur, das
  Job-Artefakt herunterzuladen und lokal zu öffnen; das funktioniert, weil die
  Datei eigenständig ist, ist aber kein Link, den man morgens aufruft. Mit
  *Pages access control* sieht sie nur, wer im Projekt ist.
* **CI-Variable `NRD_STORE_TOKEN`**: Project Access Token mit `write_repository`,
  maskiert und geschützt. Damit schreibt der Nachtlauf die Historie auf den
  Branch `nightly-data` fort. Job-Artefakte verfallen – ein Jahr Historie
  überlebt das nicht.

  Ist die Variable **geschützt**, ist sie nur in Pipelines auf geschützten
  Branches sichtbar. Der Schedule läuft auf eurem Default-Branch; ist der nicht
  geschützt, bleibt der Token leer und der Push scheitert mit einem
  Authentifizierungsfehler, der nicht danach aussieht.
* **`GIT_DEPTH: "0"`** im Nachtlauf-Job. Die Commit-Liste vergleicht gegen den
  SHA des Vorlaufs; im flachen Standard-Clone liegt der nicht vor, und die Liste
  bliebe still leer.
* Ein **Pipeline Schedule** (CI/CD → Schedules) für die Nachtzeit.

### Die Historie geht an Merge Requests vorbei

Die Daten werden zwar committet, aber **nie in den Dev-Branch**. Der Nachtlauf
pusht ausschließlich auf `nightly-data`, einen Branch, der nie gemergt wird und
nur diesen einen Zweck hat. Damit greift keine Approval-Regel: Freigaben hängen
an Merge Requests auf geschützte Branches, ein direkter Push auf einen
ungeschützten Branch läuft daran vorbei. Der Code – `nrd/` und die
`.gitlab-ci.yml` – geht dagegen ganz normal per MR in den Dev-Branch, mit euren
zwei Freigaben; danach fasst ihn niemand mehr an, während die Historie täglich
wächst. Genau deshalb bleibt es bei einem Repo: der Zwang zur Freigabe trifft
den Code, nicht die Daten.

Zwei Dinge können das trotzdem blockieren, beide in euren Projekteinstellungen:

* **Geschützte Branches mit Platzhalter.** Steht dort ein Muster wie `*`, ist
  `nightly-data` mitgeschützt und der Token-Push scheitert. Abhilfe: entweder
  das Muster so fassen, dass `nightly-data` nicht darunterfällt, oder den Branch
  ausdrücklich schützen und dem Token-Benutzer unter *Allowed to push* das
  Recht geben.
* **Push Rules** (Premium) gelten auch für CI-Pushes – etwa erzwungene
  Commit-Message-Muster oder verpflichtend signierte Commits. Der Bot-Commit
  muss dazu passen; seine Nachricht steht in der `.gitlab-ci.yml` und lässt
  sich anpassen.

Verbietet eure Instanz Bot-Pushes ins Repo grundsätzlich, gibt es zwei Auswege,
beide ohne Schreibrecht am Repository: die Historie als *Generic Package* in die
Package Registry legen (`CI_JOB_TOKEN` genügt, aber die Versionierung je Nacht
und das Wiederfinden des jüngsten Pakets müssen dann gelöst werden), oder das
Artefakt der vorherigen Pipeline über die API ziehen (fragil, weil Artefakte
verfallen). Beides ist nicht gebaut – sagt Bescheid, wenn es darauf hinausläuft,
das ist ein überschaubarer Umbau an genau einer Stelle im Job.

Scheitert das Zurückschreiben trotzdem, ist der Lauf nicht verloren: das
Job-Artefakt wird auch bei rotem Job hochgeladen (`when: always`) und enthält
`data/` samt `output.xml`, sodass sich die Nacht von Hand nachziehen lässt.

Rote Tests brechen den Job nicht ab: Robot meldet die Zahl der fehlgeschlagenen
Tests als Exitcode, erst ab 251 ist Robot selbst gescheitert. Genau das prüft
der Job – sonst gäbe es an schlechten Tagen gar keinen Lauf.

## Tests

```bash
pip install pytest && python -m pytest -q
```

49 Tests: der Collector gegen eine echte Robot-7-`output.xml` und eine
handgeschriebene im Robot-6-Format (`starttime`/`endtime`, `<metadata><item>`),
die Statuskodierung, die Versionsauflösung, die Commit-Ermittlung samt flachem
Clone, die Historie (Positionen, Ersetzen, SHA-Kette, Kappen), das Einbetten der
Fehlermeldungen und die Kette von der `output.xml` bis zur fertigen HTML.

## Was noch offen ist

* **Gegen eine echte Suite gelaufen ist das nicht.** Der Collector ist gegen
  Robot 7.4 und das ältere Format getestet, aber eure Metadaten-Konvention muss
  jemand in den Suiten setzen, und die Pipeline hat noch keine echte Instanz
  gesehen.
* Kein Link in die GitLab-Oberfläche: Commits und Pipelines stehen als SHA und
  Nummer da, nicht als Verweis. Dafür fehlt die Projekt-URL in den Daten.
* `--keep` kappt den Index, lässt die Detaildateien aber liegen. Das ist
  gewollt (Anzeigefenster vs. Archiv), heißt aber: `runs/` wächst unbegrenzt.
* `started_at` ist die Zeitangabe aus der `output.xml`, also lokale Zeit ohne
  Zone. Für die Datumszuordnung reicht das; für Zeitzonenvergleiche nicht.
* Variante C (`previews/c.html`) ist eingefroren und liegt noch auf dem alten
  Datenmodell mit einer einzelnen Release-Version.
