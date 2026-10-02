# Message Center: Pflegeanleitung

Für den, der die Integration betreut. Sie beschreibt, wo Handlungsbedarf erscheint, wie man einen Fehler eingrenzt, wie man zurückkehrt und wie eine neue Version entsteht. Zugänge zur eigenen Anlage (Adressen, Schlüssel) gehören nicht hierher, sondern in die private Ablage.

## 1 Wo Handlungsbedarf erscheint

| Ort | Was dort steht |
|---|---|
| Einstellungen → System → Reparaturen | Speicher nicht schreibbar · Verlauf nicht schreibbar (Warnung; „Bereit“ bleibt an, beendete Meldungen warten im Arbeitsspeicher, höchstens 1000) · Message Center voll (200 offene Meldungen) · Meldungen mit unklarer Zustellung · Regel kann ihre Entität nicht lesen · Regel länger aktiv als ihre Höchstdauer · Empfänger nicht erreichbar |
| Benachrichtigung in Home Assistant | „… Meldungen konnten noch nicht zugestellt werden“: Solange Zustellungen scheitern; verschwindet von selbst |
| Einstellungen → Geräte & Dienste → Message Center | „Einrichtung fehlgeschlagen, wird erneut versucht“ mit dem Grund „kann seinen Speicher nicht lesen“: Die Datei in `.storage` ist nicht lesbar oder hat ein unerwartetes Format |
| Seite, Kopf | „Bereit“ oder „Nicht bereit“ |
| Seite, Übersicht | „Gestört“ größer 0 · „Neu“ größer 0 (unbewertete Meldungen) |
| Entität „Bereit“ | aus = die Zentrale nimmt nichts an; Attribut `reason` nennt den Grund. Bei nicht schreibbarem Speicher versucht sie es alle 60 s von selbst wieder und geht ohne Neustart auf „an“ |
| GitHub, Reiter Actions | Wöchentlicher Test gegen die Mindestversion, die aktuelle und die neueste Home-Assistant-Version. Ein roter oder ausgebliebener Lauf gilt nicht als bestanden |
| Ankündigungen von Home Assistant | Abkündigungen im Log („deprecated“) und im Entwickler-Blog; umsetzen, bevor sie wirksam werden |

## 2 Einen Fehler eingrenzen

1. **Was sagt die Seite?** Reiter „Offen“ (Zustand und Grund), „Verlauf“ (Endzustand und Ereignisliste je Meldung), „Empfänger“ (letzter Fehler je Handy).
2. **Kam die Meldung überhaupt an der Zentrale an?** Steht sie weder in „Offen“ noch im „Verlauf“, hat die Automation nicht gesendet oder der Aufruf wurde abgewiesen. Im Verlauf der Automation (Traces) nachsehen: Ein Feldfehler (Titel fehlt oder zu lang, Text leer, Zusatzdaten nicht als JSON speicherbar) steht dort als Schemafehler von Home Assistant („Invalid data“), die Zentrale lief dann gar nicht. Ablehnungen der Zentrale selbst sind `store_full`, `not_ready` und bei `send` zusätzlich `priority_not_allowed` sowie `invalid_field` (nur bei unbekannter Meldungsart). Bei `snooze`, `forward`: `not_found` (auch bei einer Kennung der alten Form „Herkunft:Schlüssel“; `discard` antwortet darauf mit `discarded: 0`), bei allen dreien `Unauthorized` (Nutzer der Gruppe „Nur Lesen“).
3. **Logbuch:** Zustellungen und Eingriffe stehen dort mit Herkunft und Titel.
4. **Log von Home Assistant:** nach `message_center` suchen. Die Zentrale schreibt nie Titel, Text, Notiz oder Kennung ins Log, nur Fehlerklassen, Entitäten, Aktionsnamen und Zahlen. Mehr Einzelheiten liefert vorübergehend:

   ```yaml
   logger:
     logs:
       custom_components.message_center: debug
   ```

   Die Zeilen und ihre Bedeutung:

   | Zeile | Bedeutung |
   |---|---|
   | ERROR `Message store not writable: …` | Der Arbeitsspeicher ließ sich nicht bestätigt schreiben (einmal je Störung; dazu von Home Assistant je Fehlversuch `Error writing config for message_center.messages`). „Bereit“ ist aus |
   | INFO `Message store writable again` | Die Störung ist vorbei, „Bereit“ wieder an |
   | WARNING `History store not writable: …` | Die Verlaufsdatei ließ sich nicht schreiben (einmal je Störung); Reparaturhinweis, Einträge warten im Arbeitsspeicher |
   | INFO `History store writable again` | Verlauf wieder geschrieben, Hinweis weg |
   | WARNING `Pending history at its limit of N entries: M oldest dropped` | Mehr als 1000 beendete Meldungen warteten auf den Verlauf; die ältesten wurden aus der Warteliste verdrängt und können verloren gegangen sein |
   | ERROR `Unexpected error pushing to <Aktion>: <Fehlerklasse>` mit Aufrufstapel | Ein Push ist mit einem unerwarteten Fehler gescheitert (nicht Aktion fehlt / ungültige Daten / Home-Assistant-Fehler); zählt als gescheiterter Versuch |
   | WARNING `Script <Entität> (<Zweck>) failed: <Fehlerklasse>` | Wirkungs- oder Weiterleiten-Skript gescheitert; Vermerk `script_failed` |
   | WARNING `Light pulse refused: no right to […]`, `Alarm light refused: no right to […]`, `Alarm light not restored: no right to […]` | Der Auslöser der Meldung (oder der Bediener des Schalters „Alarm“) darf die Lampen nicht schalten; Vermerk `light_failed` |
   | WARNING `Light pulse <Dienst> on […] failed: …` | Ein Lichtbefehl ist aus einem anderen Grund gescheitert (Lampe nicht erreichbar) |
   | INFO `Push button <Knopfart> ignored: <Fehlerklasse>` | Ein Knopf vom Handy ließ sich nicht ausführen (Meldung nicht mehr da: `NotFoundError`; Zentrale nicht bereit oder gerade neu geladen: `NotReadyError`; der Nutzer des Handys darf nur lesen oder ist deaktiviert: `Unauthorized`; der Nutzer des Handys ist gelöscht: `UnknownUser`, nur als Absicherung, weil Home Assistant mit dem Nutzer auch die Registrierung des Handys entfernt) |
   | INFO `Alarm light started by …` / `Alarm light ended by …` | Alarmlicht an und aus, mit Auslöser |

5. **Diagnose-Download:** Einstellungen → Geräte & Dienste → Message Center → Diagnose herunterladen. Enthält Optionen, Meldungsarten, Regeln und die Meldungen als Zusammenfassung, **ohne Texte, aber mit Titeln**. Vor dem Weitergeben durchlesen.
6. **Nachstellen:** Test-Knopf je Stufe in den Einstellungen (ohne Verlauf), oder in den Entwicklerwerkzeugen `notify.message_center` mit Titel und Text aufrufen (Herkunft dann „unbekannt“).

**Typische Ursachen**

| Befund | Ursache |
|---|---|
| Meldung wartet „zurückgehalten: ‹Regel›“ | Zustellregel aktiv; so gewollt, oder der Meldungsart fehlt „Nicht zurückhalten“. Gilt auch im Zustand „wiederholen“: Eine fällige Wiederholung wartet auf das Regelende, `next_try` ist dann leer; „Jetzt senden“ schickt sie sofort |
| Meldung „verworfen“ mit Grund Regel, obwohl sie schon bei einem Handy war | Nein: Hat ein Handy die Meldung, endet eine verwerfende Regel den Zyklus als „zugestellt“ mit gescheiterten Empfängern. „Verworfen“ nur, wenn kein Handy sie hatte |
| Meldung wartet „Mindestabstand bis …“ | Abstand der Meldungsart |
| Meldung „verfallen“ | Verfall der Meldungsart war kürzer als die Wartezeit |
| Bekannte Meldung unter „Neu“ | Titel in der Automation geändert, Titelbedingung passt nicht mehr |
| Fehler `ServiceNotFound` am Empfänger | Das Handy heißt anders oder die App ist abgemeldet; Empfänger im Reiter „Empfänger“ neu wählen |
| „unklar“ nach Neustart | Neustart während des Sendens oder Lücke über 60 Minuten; von Hand entscheiden |
| `script_failed` unter einer Meldung | Das gewählte Skript fehlt, hat einen Fehler oder braucht länger als 30 Sekunden |
| `script_skipped`, `light_skipped` mit Grund `effect` | Die Meldung kam aus einer eigenen Wirkung der Zentrale (Skript, Lichtimpuls, Alarmlicht, Test-Knopf oder eine Automation darauf; Feld `from_effect`). Sie wird zugestellt, bekommt aber kein Skript, keinen Lichtimpuls und kein Alarmlicht (Tiefe 1). Das Zustellereignis, das Ereignis `forwarded` und der Push selbst zählen nicht als eigene Wirkung |
| `light_failed` unter einer Meldung | Home Assistant hat den Lichtbefehl verweigert: Der gespeicherte Nutzer der Meldung darf die Lampen nicht schalten oder wurde gelöscht. Der Push kam trotzdem |
| Nach dem Update erscheint eine Wiederholung als zweiter Push neben dem alten | Der alte Push trägt noch den Tag der alten Kennung; einmalig je Meldung |
| Meldung nach Neuladen der Integration „unklar“, obwohl der Push ankam | Der Push war beim Neuladen gerade unterwegs; die alte Zentrale verbucht nach dem Stopp nichts mehr. Auf der Seite entscheiden |

## 3 Zurückkehren

Ziel ist die letzte funktionierende Kombination aus Code, Einstellungen und Daten.

- **Vor jedem Update ein Backup**, bei Home Assistant wie bei HACS. Nur aktualisieren, wenn man danach erreichbar ist.
- **Vor dem Update auf 0.11.0 unbedingt ein Backup:** 0.11 hebt den Arbeitsspeicher `.storage/message_center.messages` beim ersten Start einmalig auf Formatversion 2 (Salz `id_salt`, Nachrichten und Abstände unter der neuen Kennung). 0.10.5 lehnt diese Datei sichtbar als „Speicher nicht lesbar“ ab. Der Rückweg auf 0.10.5 ist nur das Backup, und zwar **beide** Dateien `message_center.messages` und `message_center.history` zusammen: Nur der Arbeitsspeicher trägt das Salz; wird nur eine der beiden Dateien wiederhergestellt (oder nur der Arbeitsspeicher geht verloren), entsteht ein neues Salz, und die Verlaufseinträge aus 0.11 behalten ihre alten Kennungen. Es bricht dann nichts, aber die Zuordnung alt/neu über die Kennung ist weg.
- **Code zurück:** In HACS bei „Message Center“ über „Erneut herunterladen“ eine ältere Version wählen (HACS bietet die letzten fünf Releases), dann Home Assistant neu starten.
- **Einstellungen und Daten zurück:** aus dem Backup. Die Einstellungen (Empfänger, Meldungsarten, Gruppen, Regeln, Optionen) liegen im Config Entry, die Meldungen in `.storage/message_center.messages` und `.storage/message_center.history`. Wird die Integration gelöscht, löscht sie diese beiden Dateien mit; die Blueprint-Datei bleibt.
- **Nach der Rückkehr zu einem älteren Backup** gelten offene Meldungen als „unklar“, wenn die Lücke über 60 Minuten liegt. Abgelaufene Fristen werden nicht wiederbelebt, nichts wird blind noch einmal gesendet.
- **Ganz ohne Message Center weiter:** In den Automationen das Ziel wieder auf das Handy stellen (`notify.mobile_app_…`). Wer das Blueprint „Nachricht senden (mit Rückfall)“ nutzt, bekommt die Meldungen ohnehin weiter, auch wenn die Integration fehlt: als Benachrichtigung in Home Assistant und, falls gewählt, roh an das Ersatzziel.
- **Home Assistant startet nicht mehr:** Den Ordner `custom_components/message_center` umbenennen und neu starten. Die Automationen melden dann einen Fehler statt zu senden, sonst läuft alles weiter.

## 4 Eine neue Version

1. Änderung mit Test. Was einen veröffentlichten Anschluss betrifft (README, Abschnitt „Interfaces and their contracts“), wird ab 1.0 nur erweitert, nie umgedeutet; bis 1.0 darf er sich noch ändern, die Änderung wird dann im CHANGELOG als **Contract change** markiert.
2. Version anheben in `custom_components/message_center/manifest.json`, `frontend/package.json` und `frontend/package-lock.json` (dort zweimal). `tests/test_repository_files.py` prüft, dass die drei übereinstimmen und zum Kopf des CHANGELOG passen. Die Version steht in der Adresse des Seitencodes (`panel.py` hängt sie als `?v=` an); ohne Versionssprung zeigt der Browser die alte Seite aus dem Cache.
3. Seite bauen, wenn sich `frontend/src/` geändert hat: `cd frontend && npm run check && npm run build`. Die beiden erzeugten Dateien in `custom_components/message_center/frontend/` mit einchecken; die CI prüft, dass sie zum Quellcode passen.
4. Prüfen: `.venv/bin/pytest`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`
5. Eintrag im `CHANGELOG.md`. Wird die Mindestversion in `hacs.json` angehoben, gehört das dazu.
6. Commit, Push, CI abwarten. Dann Tag und **Release** auf GitHub: Ab 0.11.1b1 ist jede Version ein GitHub-Release (HACS zeigt Releases, nicht bloße Tags).
7. Auf einer Test-Installation oder der eigenen Installation aktualisieren, „Bereit“ abwarten, Log auf Fehler prüfen, Seite ansehen.

**Vor jeder Veröffentlichung** auf persönliche Daten und Geheimnisse prüfen: Quelltext, Tests, Beispiele, Screenshots, Git-Verlauf, CI-Ausgaben. Im Repository stehen nur ausgedachte Beispieldaten. Dazu von Hand prüfen, dass im ganzen Git-Verlauf als Autor- und Committer-Adresse nur die GitHub-noreply-Adresse steht:

```bash
git log --all --format='%an <%ae> %cn <%ce>' | sort -u
```

Die Ausgabe darf nur Adressen mit `@users.noreply.github.com` enthalten. Taucht eine andere Adresse auf, den Verlauf vor der Veröffentlichung umschreiben. Das ist bewusst kein Test in `pytest`: Der Git-Verlauf gehört nicht zum Code.

**Einstellungen des Repositorys auf GitHub:** Der HACS-Job in `.github/workflows/validate.yml` prüft außer den Dateien auch Einstellungen des Repositorys: eine Beschreibung, Topics (etwa `home-assistant`, `hacs`, `integration`) und aktivierte Issues. Fehlt eines davon, ist „Validate“ rot. Beim Anlegen eines Repositorys diese Einstellungen vor dem ersten Push setzen, Issues aktiviert lassen und den ersten Lauf des HACS-Jobs bewusst ansehen.

## 5 Home-Assistant-Updates

- Die CI testet wöchentlich gegen die Mindestversion (`hacs.json`), die aktuelle Version (`requirements_test.txt`) und die neueste Ausgabe der Testbibliothek, die auch Betas abbildet.
- **Vor einem Update von Home Assistant** die Zielversion in `requirements_test.txt` eintragen (passende Ausgabe von `pytest-homeassistant-custom-component` und das Frontend-Paket, das diese Version verlangt) und die Tests laufen lassen. Schlägt ein Test fehl, wird die Integration angepasst oder das Update aufgeschoben.
- Empfindliche Stellen, weil sie über die stabilen Schnittstellen hinausgehen: die Elemente der Home-Assistant-Oberfläche, die die Seite verwendet (`ha-dialog`, `ha-button`, `ha-form`), das Zusatzmodul für das Symbol in der Seitenleiste (`window.customIcons`), die Untereinträge des Config Entry und das Format der Companion-App-Pushs.

## 6 Bekannte offene Punkte

- Der Arbeitsspeicher `message_center.messages` hat Formatversion 2 (seit 0.11.0, mit getesteter Migration von 1 an einer festen 0.10.5-Datei); der Verlaufsspeicher `message_center.history` bleibt bei Version 1, alte Einträge ohne Kennung laden weiter und bekommen sie beim Lesen. Eine Datei der Version 2 ohne Salz, eine Nachricht ohne oder mit fremder Kennung oder ein beschädigter Verlaufseintrag ergeben „Speicher nicht lesbar“ mit Grund und erneutem Versuch.
- **Übergang alter Knopfkennungen:** Die Knöpfe „Später“ und „An KI“ auf Pushs, die vor 0.11 zugestellt wurden, tragen die Kennung der alten Form `Herkunft:Schlüssel`. Nur der Knopfweg (`center.py`, `_on_notification_action`) bildet sie noch auf die neue ab, im Code mit „remove with 0.12“ markiert; mit 0.12 entfernen. Die Aktionen und die Seite nehmen nur die neue Form.
- Nicht automatisch getestet: ein Neustart von Home Assistant mitten im Alarmlicht.
- **Blueprint aktualisieren:** Die Datei `blueprints/script/message_center/nachricht_senden.yaml` wird nie überschrieben. Bringt eine neue Version ein geändertes Blueprint mit (siehe CHANGELOG), die Datei löschen und Home Assistant neu starten; die Integration kopiert dann die aktuelle. Eigene Änderungen an der Datei gehen dabei verloren.
- Ein Ersatzziel im Blueprint, das es nicht mehr gibt (Handy umbenannt), fällt nur im Log auf: „Action notify.mobile_app_… not found“. Der Absender bekommt trotzdem `fallback` und die Benachrichtigung in Home Assistant.
- Ist der Speicher unschreibbar, versucht jeder direkte Aufruf (`notify`, `send`, `discard`, `snooze`, `forward`) einmal zu schreiben (Probe-Schreiben) und die Zentrale außerdem alle 60 s von selbst. Bis dahin lehnt sie diese Aufrufe ab; was außerhalb eines Aufrufs fällig wird (Regelende, Wiederholung, Push-Ergebnis, „Jetzt senden“, Start), wird trotzdem gesendet, auf die Gefahr hin, dass die Meldung nach einem Neustart noch einmal kommt. Jeder Schreibvorgang wird durch Rücklesen bestätigt (Schreibmarke `write_id`). Bei anhaltendem schnellem Schreibfehler entsteht so je direktem Aufruf und je 60-s-Versuch eine Fehlerzeile von Home Assistant.
- Grenzen rund um das Schreiben: Während Home Assistant herunterfährt, gilt ein Schreiben als bestätigt und bleibt dem letzten Schreibvorgang von Home Assistant überlassen. Ein Schreiben, das in die 5-s-Grenze lief, kann danach noch auf der Platte landen; die abgelehnte Meldung steht dann dort, bis die Zentrale wieder schreibt. Nach so einer Zeitüberschreitung lehnen die direkten Aufrufe bis zu 60 s sofort ab, ohne Probe-Schreiben. Bei hängender Platte verzögert sich jeder Push außerhalb eines Aufrufs um bis zu 5 s (schreiben vor senden). Ein beim Herunterfahren abgebrochener Aufrufer lässt seinen Versuch vorgemerkt; eine abgebrochene Wiederholung wird wieder fällig, ein abgebrochener erster Push bleibt bis zum Neustart in „sende“ (dann „unklar“).
- Scheitert nur der Verlaufsspeicher, warten höchstens 1000 beendete Meldungen im Arbeitsspeicher (`pending_history`); darüber gehen die ältesten verloren, und jeder Schreibvorgang des Arbeitsspeichers wird größer.
- Tiefe 1 (`from_effect`) stoppt nur die eigenen Wirkungen der Zentrale: Automationen auf das Zustellereignis, auf `forwarded` oder auf den Push selbst sowie Ketten über äußere Systeme sind nicht begrenzt. Eine Mengenbremse ist für nach 1.0 vorgemerkt. Die Kontexte der eigenen Wirkungen liegen nur im Arbeitsspeicher des Prozesses (höchstens 1000, nach dem Neustart leer).
- Lichtbefehle laufen im Kontext des Auslösers; Home Assistant prüft die Rechte an den Lampen. Ohne Recht (oder bei gelöschtem Nutzer) bleibt das Licht aus, der Push geht. Ein eigener Push-Knopf des Absenders, dessen Aktion mit `message_center_alarm_off` beginnt, wird wie der Alarmknopf an die dritte Stelle gerückt.
