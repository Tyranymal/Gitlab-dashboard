# Layout-Vorschauen

Drei Entwürfe für das Nachtlauf-Dashboard, alle auf demselben synthetischen Datensatz.
Jede Datei ist eigenständig: kein Server, kein CDN, keine Netzwerkanfrage – Doppelklick
genügt. Das ist keine Bequemlichkeit, sondern Voraussetzung: interne GitLab-Instanzen
haben im Browser-Kontext oft keinen Internetzugang.

| Datei | Variante | Stand |
|---|---|---|
| `b.html` | **Master / Detail** – gewählt | aktuell, mit Microservice-Versionen |
| `a.html` | Timeline mit Versionsband | eingefroren, einzelne Release-Version |
| `c.html` | Test-×-Nacht-Matrix | eingefroren, einzelne Release-Version |

`a.html` und `c.html` bleiben als Referenz liegen. Sie enthalten ihre Daten inline und
rendern weiterhin, gehen aber noch von *einer* Release-Version aus – der Annahme, die
sich als falsch herausgestellt hat. Ihre Templates liegen unter `_archived/`.

## Neu bauen

```bash
python3 gen_demo.py        # erzeugt demo-data.json
python3 build_previews.py  # templates/ + shared/ + Daten -> b.html
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
