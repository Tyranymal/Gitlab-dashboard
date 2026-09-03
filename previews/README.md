# Layout-Vorschauen

Drei Entwürfe für das Nachtlauf-Dashboard, alle auf demselben synthetischen Datensatz.
Jede Datei ist eigenständig: kein Server, kein CDN, keine Netzwerkanfrage – Doppelklick
genügt. Das ist keine Bequemlichkeit, sondern Voraussetzung: interne GitLab-Instanzen
haben im Browser-Kontext oft keinen Internetzugang.

| Datei | Variante | Stand |
|---|---|---|
| `a.html` | **Timeline (Balkendiagramm)** – gewählt | aktuell, mit Microservice-Versionen |
| `b.html` | Master / Detail | aktuell, mit Microservice-Versionen |
| `c.html` | Test-×-Nacht-Matrix | eingefroren, einzelne Release-Version |

Screenshots der drei Varianten liegen unter `screenshots/` – zum Verschicken, wenn der
Empfaenger die HTML-Dateien nicht selbst oeffnen will.

`c.html` bleibt als Referenz liegen. Die Datei enthält ihre Daten inline und rendert
weiterhin, geht aber noch von *einer* Release-Version aus – der Annahme, die sich als
falsch herausgestellt hat. Ihr Template liegt unter `_archived/`.

## Was Variante A zeigt

Über dem Balkendiagramm liegt kein Release-Band mehr, sondern ein Ereignisband: je Nacht
ein Kästchen pro Service, der in neuer Version lief. Die Höhe des Stapels ist damit die
Zahl der Sprünge, und durch jede Nacht mit Sprung läuft eine Senkrechte durch beide
Diagramme – erst dadurch lässt sich ein Ausschlag einem Sprung zuordnen, ohne zwischen
zwei Grafiken hin und her zu messen.

Unter dem Diagramm steht eine Datumsleiste. Sie blättert nachtweise (`◀ Nacht`), springt
von Versionsereignis zu Versionsereignis (`◀◀ Sprung`) und zurück auf die neueste Nacht.
Alles darunter – Commits, Status-Wechsel, Versionswechsel – sowie die Kennzahlen oben
folgen der Auswahl; ist nicht die neueste Nacht gewählt, sagt das die Kopfzeile der
Hero-Kachel. Balken anklicken und ← → im fokussierten Diagramm tun dasselbe.

Liegt zum Vorlauf ein Versionswechsel vor, steht er direkt in der Leiste ausgeschrieben –
„Neue Version gegenüber Mi 02.09.2026: `ingest-service 7.2.1 → 7.3.0` minor" –, sonst
„Keine Versionsänderung gegenüber …". Dasselbe ausführlich in der Card *Versionswechsel
zum Vorlauf*. Verglichen wird immer mit dem vorherigen **Lauf**, nicht mit dem Vortag; ist
dazwischen eine Nacht ausgefallen, steht das als Hinweis daneben, sonst liest man einen
Zweitagessprung als Änderung über Nacht.

Die Chronik am Seitenende führt jeden der 31 Versionssprünge als eigene Zeile: Nacht,
Service, `vorher → nachher`, Art des Sprungs und der Abstand zum vorherigen Sprung
desselben Service. Datum anklicken wählt die Nacht oben aus; die Zeilen der gewählten
Nacht sind markiert, die Leiste darüber filtert auf einen Service.

## Neu bauen

```bash
python3 gen_demo.py        # erzeugt demo-data.json
python3 build_previews.py  # templates/ + shared/ + Daten -> b.html
node shoot_previews.mjs    # a/b/c.html -> screenshots/*.png (Playwright + Chromium)
```

## Der Datensatz

58 Nächte (zwei Läufe fehlen absichtlich – der Diff muss den vorherigen *Lauf*
vergleichen, nicht „gestern"), 214 Tests, sieben Microservices mit unabhängigen
Versionsspuren, ein Regressionscluster, das an einem `calibration-svc`-Sprung hängt,
zwei Tests mit `fail:`-Tag die wieder laufen, sechs später hinzugekommene und vier
entfallene Tests.

Kompaktes Format: statt 58 × 214 Testobjekten gibt es eine Testliste und je Lauf einen
String mit einem Zeichen pro Test (`P` pass · `p` pass mit `fail:`-Tag · `f` bekannter
Fail · `F` neuer Fail · `-` nicht im Lauf). Dieselbe Idee wie die spätere Trennung von
`index.json` und `runs/*.json`.

## Farben

Die Stapelreihenfolge grün → gelb → violett → rot ist mit dem Palette-Validator geprüft
(Light und Dark, CVD- und Normalsicht-Trennung bestanden). Violett statt Orange für
„bekannter Fail", weil Orange neben Gelb unter Rot-Grün-Schwäche zusammenfällt.
Die Versionsbänder nutzen einen ordinalen Blau-Ramp – Versionen sind geordnet, und die
Farbe kann so nie mit einer Statusfarbe verwechselt werden.
