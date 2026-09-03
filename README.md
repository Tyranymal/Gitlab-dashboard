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

Fehlt das, sucht der Collector in der Suite-Dokumentation nach Zeilen der Form
`name: 1.2.3`. Was aus welcher Quelle stammt, steht als `version_source` am Lauf
(`metadata`, `suite_doc`, `mixed`, `none`) – damit niemand eine aus der Doku
geschätzte Version für einen Build-Fakt hält. Als Version zählt nur, was
mindestens einen Punkt hat; eine nackte Pipeline-Nummer rutscht so nicht durch.

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
Dauer. Das Dashboard nutzt es noch nicht; es entsteht trotzdem bei jedem Lauf,
weil sich Fehlermeldungen nachträglich nicht rekonstruieren lassen.

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
* **`GIT_DEPTH: "0"`** im Nachtlauf-Job. Die Commit-Liste vergleicht gegen den
  SHA des Vorlaufs; im flachen Standard-Clone liegt der nicht vor, und die Liste
  bliebe still leer.
* Ein **Pipeline Schedule** (CI/CD → Schedules) für die Nachtzeit.

Rote Tests brechen den Job nicht ab: Robot meldet die Zahl der fehlgeschlagenen
Tests als Exitcode, erst ab 251 ist Robot selbst gescheitert. Genau das prüft
der Job – sonst gäbe es an schlechten Tagen gar keinen Lauf.

## Tests

```bash
pip install pytest && python -m pytest -q
```

44 Tests: der Collector gegen eine echte Robot-7-`output.xml` und eine
handgeschriebene im Robot-6-Format (`starttime`/`endtime`, `<metadata><item>`),
die Statuskodierung, die Versionsauflösung, die Commit-Ermittlung samt flachem
Clone, die Historie (Positionen, Ersetzen, SHA-Kette, Kappen) und die Kette von
der `output.xml` bis zur fertigen HTML.

## Was noch offen ist

* **Gegen eine echte Suite gelaufen ist das nicht.** Der Collector ist gegen
  Robot 7.4 und das ältere Format getestet, aber eure Metadaten-Konvention muss
  jemand in den Suiten setzen, und die Pipeline hat noch keine echte Instanz
  gesehen.
* Die Detaildateien werden geschrieben, aber noch nicht angezeigt – der nächste
  sinnvolle Schritt wäre, die Fehlermeldung eines Tests im Dashboard
  aufzuklappen.
* Kein Link in die GitLab-Oberfläche: Commits und Pipelines stehen als SHA und
  Nummer da, nicht als Verweis. Dafür fehlt die Projekt-URL in den Daten.
* `--keep` kappt den Index, lässt die Detaildateien aber liegen. Das ist
  gewollt (Anzeigefenster vs. Archiv), heißt aber: `runs/` wächst unbegrenzt.
* `started_at` ist die Zeitangabe aus der `output.xml`, also lokale Zeit ohne
  Zone. Für die Datumszuordnung reicht das; für Zeitzonenvergleiche nicht.
* Variante C (`previews/c.html`) ist eingefroren und liegt noch auf dem alten
  Datenmodell mit einer einzelnen Release-Version.
