# Message Center: Bedienhilfe

Kurz und für den Alltag. Die vollständige Beschreibung mit allen Anschlüssen steht in der [README](../README.md) (englisch).

## Worum es geht

Automationen schicken ihre Meldungen nicht mehr direkt ans Handy, sondern an das Message Center. Das entscheidet, ob eine Meldung sofort kommt, später oder gar nicht, fasst Wiederholungen zusammen und zeigt alles auf einer Seite in der Seitenleiste. Die Automationen wissen davon nichts: Sie liefern nur Titel und Text.

## Einrichtung

1. **Hinzufügen:** Einstellungen → Geräte & Dienste → Integration hinzufügen → „Message Center“. Die Handys ankreuzen, die Meldungen bekommen sollen (mindestens eines, mit der Home-Assistant-App).
2. **Seite öffnen:** „Message Center“ in der Seitenleiste. Die Seite sehen nur Administratoren. Die Einführungskarte in der Übersicht erklärt die fünf Grundgedanken; sie lässt sich ausblenden und in den Einstellungen wieder einblenden.
3. **Absender umstellen:** In jeder Automation, die bisher ans Handy meldet, die Aktion durch `notify.message_center` ersetzen. Im Automationseditor bei *Aktion hinzufügen* oben nach „Message Center“ suchen. Gemeint ist der Eintrag, der nur „Message Center“ heißt, nicht „Message Center: Senden“. Ein **Titel** ist gut, aber nicht Pflicht: Ohne Titel heißt die Meldung wie die Automation (siehe „Der Titel entscheidet“). Welche Stellen noch direkt senden, zeigt der Knopf **„HA durchsuchen“** im Reiter „Meldungen“; je Fundstelle steht dort, was zu ändern ist, und ob ein eigener Titel nötig ist. Bei Fundstellen in Dateien zeigt die Suche nur Datei, Zeilennummer und Aktionsname, nie die Zeile selbst (sie könnte ein Passwort enthalten).

   ```yaml
   - action: notify.message_center
     data:
       title: "Feuchte: Büro"
       message: "Seit zwei Stunden über 62 %. Bitte lüften."
   ```

4. **Bewerten:** Jede neue Sorte Meldung erscheint in der Übersicht unter „Neu, bitte bewerten“. „Bewerten“ macht daraus eine **Meldungsart**: Stufe, Gruppe, Abstand, Verfall (siehe „Der Dialog einer Meldungsart“). Bis dahin kommt die Meldung als Stufe 1 an; auf dem Handy steht am Ende „⚠ Noch nicht eingeordnet – bitte im Message Center bewerten“.
5. **Zustellregel anlegen (wenn gewünscht):** Reiter „Zustellregeln“. Beispiel Nachtruhe: Schalter „Nachtmodus“ = an → Stufe 1 und 2 zurückhalten, Stufe 3 durchlassen, höchstens 12 Stunden. Den Schalter kann der Dialog der Regel gleich mit anlegen (siehe „Modi“).
6. **Ausprobieren:** Reiter „Einstellungen“, Knopf „Test“ je Stufe. Dort auch die Lampen für den Lichtimpuls und das Alarmlicht wählen. Solange dort etwas nicht gespeichert ist, steht bei jeder Stufe „Speichern“ statt „Test“: Ein Test nutzt immer den gespeicherten Stand.

### Der Titel entscheidet

Das Message Center erkennt eine Meldung an **Herkunft und Titel**. Deshalb:

- Soll jeder Raum eine eigene Meldung sein, gehört der Raum in den Titel, die Art nach vorn: „Feuchte: Büro“, „Feuchte: Küche“. Eine Meldungsart mit „beginnt mit Feuchte“ gilt dann für alle Räume.
- Steht der Raum nur im Text, ist es eine einzige Meldung; die spätere ersetzt die frühere.
- Wer einen Titel in einer Automation ändert, muss die Titelbedingung der Meldungsart mit ändern. Sonst taucht die Meldung wieder unter „Neu“ auf.
- **Ohne Titel** heißt die Meldung wie ihre Automation (bei einem Skript wie die Automation, die es startet, ohne startende Automation wie das Skript); nur bei unbekannter Herkunft, etwa aus den Entwicklerwerkzeugen, heißt sie „Mitteilung“. Wird die Automation umbenannt, ist es eine neue Meldung.
- Schickt eine Automation nur **eine** Meldung, genügt die Bedingung **„alle Meldungen dieser Automation“**: Der Titel spielt dann keine Rolle, auch nicht nach einer Änderung.

### Der Dialog einer Meldungsart

- Oben steht in Klartext, worauf die Meldungsart passt, zum Beispiel: *Gilt für: alle Meldungen der Automation „Waschmaschine“*.
- Kommt der Dialog aus „Neu“, aus „HA durchsuchen“ oder zum Bearbeiten, prüft Message Center, ob die Automation eine oder mehrere verschiedene Meldungen schickt. Bei **einer** steht die Bedingung auf „alle Meldungen dieser Automation“, und man wählt nur Stufe, Gruppe und so weiter. Bei **mehreren** ist das Titelfeld offen, mit einem roten Hinweis und den möglichen Meldungen darunter (feste Titel, berechnete mit „…“ und die bisher angekommenen).
- **Herkunft und Titel** sind sichtbar, aber ausgegraut. Sie dienen nur der Zuordnung; „Bedingung bearbeiten (erweitert)“ macht sie bearbeitbar, normalerweise ist das nicht nötig.
- Unten zeigt der Dialog, auf welche Meldungen aus „Neu“ und dem Verlauf die Bedingung passt, warnt bei „passt auf keine bisherige Meldung“ und nennt bei einer Überschneidung die Meldungsart, die gewinnt.
- Eine Bedingung, die eine andere Meldungsart schon hat (auch eine ausgeschaltete), wird abgelehnt, mit dem Link „Vorhandene bearbeiten“. Würde eine geänderte Bedingung die Meldung, aus der die Art entstand, nicht mehr treffen, fragt „Speichern“ nach.
- Eine ganz neue Meldungsart ohne Vorlage kann oben über *Aus „Neu“ übernehmen* Herkunft und Titel eines Eintrags aus „Neu“ übernehmen.
- **Verwaist** heißt: Die Automation der Meldungsart gibt es nicht mehr. Sie steht ausgegraut in der Liste, wirkt auf nichts und kann gelöscht werden.

### Modi

Ein Modus ist ein Helfer-Schalter in Home Assistant, etwa „Nachtmodus“, „Urlaub“ oder „Abwesend“. Eine Zustellregel schaut nur auf seinen Zustand. Der Dialog einer Zustellregel erklärt das unter „Was ist ein Modus?“.

- **Anlegen:** normalerweise unter Einstellungen → Geräte & Dienste → Helfer → Helfer erstellen → Schalter. Oder im Dialog der Regel mit **„Schalter anlegen“**: Name eingeben (Vorschlag „Nachtmodus“), „Anlegen“, und der Schalter ist in der Regel gleich ausgewählt.
- **Bedienen:** Der Schalter wird hier nicht bedient. Ein- und ausschalten musst du ihn über eine Automation oder im Dashboard. Message Center legt ihn nur an, schaltet ihn nie und legt auch keine Automation an.
- **Ins Dashboard holen:** geht in ein eigenes Dashboard (Einstellungen → Dashboards): „Dashboard bearbeiten“ → „Karte hinzufügen“ → „Nach Entität“ → den Schalter wählen.
- **Ideen zum Schalten:** Ein Bettschalter macht die Lampen aus und den Nachtmodus an, morgens geht der Nachtmodus wieder aus. Wer die Wohnung verlässt, schaltet „Abwesend“ an.

### Die drei Stufen

| Stufe | Wirkung |
|---|---|
| 1 Hinweis | Push aufs Handy |
| 2 Wichtig | Push und Lichtimpuls: Die gewählten Lampen gehen kurz aus und wieder an |
| 3 Alarm | Push, der „Nicht stören“ umgeht, dazu das Alarmlicht, bis jemand den Alarm beendet |

Je Stufe lässt sich zusätzlich ein eigenes Skript hinterlegen, etwa für eine Ansage über Lautsprecher.

## Alltag

**Auf dem Handy**

- **Später** stellt die Meldung zurück; sie kommt nach der Zeit auf dem Knopf wieder.
- **An KI** reicht die Meldung weiter (nur sinnvoll, wenn in den Einstellungen ein Skript dafür gewählt ist). Eine getippte Notiz geht mit; Zeichen, die sich nicht speichern lassen, werden durch „?“ ersetzt.
- **Alarm beenden** stoppt das Alarmlicht.
- Reihenfolge der Knöpfe: erst die eigenen Knöpfe der Automation, dann „Später“, dann „An KI“; bei einem Alarm steht „Alarm beenden“ spätestens an dritter Stelle. Android zeigt nur drei Knöpfe, das iPhone alle. Auf Android fällt bei einem Alarm also zuerst „An KI“ weg, dann „Später“.
- Kommt dieselbe Meldung noch einmal, ersetzt sie die alte und trägt einen Zähler: „2x Feuchte: Büro“.
- **Antippen** öffnet, was unter Einstellungen → „Knöpfe auf dem Push“ → „Beim Antippen öffnen“ steht: **Home Assistant** (Vorgabe) wie bisher, oder **Message Center** mit genau dieser Meldung aufgeklappt. Hat die Automation selbst ein Ziel mitgegeben (`clickAction` oder `url`), gilt ihres. Die Seite ist nur für Administratoren, deshalb öffnen die Handys anderer Nutzer immer Home Assistant.
- **„⚠ Noch nicht eingeordnet – bitte im Message Center bewerten“** steht am Ende einer Meldung, für die es noch keine Meldungsart gibt. Antippen öffnet direkt den Dialog zum Bewerten, egal was bei „Beim Antippen öffnen“ steht (außer die Automation gibt selbst ein Ziel mit; die Handys anderer Nutzer öffnen Home Assistant). Die Zeile steht nur im Push, nicht im gespeicherten Text, und fällt weg, sobald die Meldung eine Meldungsart hat.
- Gelesene Meldungen einfach wegwischen. Das Message Center löscht nie etwas vom Handy und braucht auch keine Bestätigung.

Die Knöpfe wirken nur, wenn das Handy Home Assistant erreicht: im Heimnetz, per VPN oder über Home Assistant Cloud. „Später“ und „An KI“ prüfen dasselbe Recht wie die Aktionen: Gehört das Handy einem Nutzer, der nur lesen darf oder deaktiviert ist, passiert beim Antippen nichts (die Knöpfe sind trotzdem zu sehen). „Alarm beenden“ wirkt von jedem Handy aus, dessen App Home Assistant erreicht.

**Auf der Seite**

| Reiter | Wofür |
|---|---|
| Übersicht | Was gerade ansteht und wie die Anlage läuft; neue Meldungen bewerten |
| Offen | Alles, was noch nicht durch ist, mit Grund und Frist. „Jetzt senden“ umgeht die Regel (auch bei „wiederholen“: die Handys, die die Meldung noch nicht haben, werden sofort versucht), „Verwerfen“ beendet ohne Zustellung |
| Verlauf | Was zugestellt, verworfen oder gescheitert ist, samt Eingriffen. Die Spalte „Zeit“ zeigt, wann die Meldung endete, immer mit Datum und Uhrzeit; „Neueste zuerst“ oder „Älteste zuerst“ merkt sich der Browser. Im Reiter „Offen“ heißt die Spalte „Seit“ |
| Meldungen | Gruppen und Meldungsarten anlegen und ändern; „HA durchsuchen“ |
| Zustellregeln | Wann zurückgehalten wird; „Was ist ein Modus?“ und „Schalter anlegen“ im Dialog |
| Empfänger | Welche Handys Meldungen bekommen, ob sie erreichbar sind |
| Einstellungen | Wirkung je Stufe, Lampen, Alarm, Knöpfe, Optionen, Test. Die Lampen für den Lichtimpuls stehen in einer Liste; jede hat einen eigenen Schalter „auch wenn aus“ (dann geht sie kurz an und wieder aus, wenn sie aus ist) |

**Ohne die Seite** geht das Wichtigste auch: Die Entitäten „Offen“, „Gestört“, „Neu“ und „Aktive Regeln“ am Gerät „Message Center“ zeigen den Stand, das Logbuch die Zustellungen und Eingriffe (mit dem Namen dessen, der eingegriffen hat). Der Schalter „Lichtimpuls“ schaltet das Blinken ab, der Schalter „Alarm“ beendet einen Alarm. Die Aktionen `message_center.discard`, `snooze` und `forward` dürfen Administratoren, normale Nutzer und Automationen; Nutzer der Gruppe „Nur Lesen“ werden abgelehnt.

**Vermerke unter einer Meldung** (Reiter „Offen“ und „Verlauf“)

| Vermerk | Bedeutung |
|---|---|
| Lichtimpuls übersprungen: Mindestabstand / keine Lampe an | Der Abstand aus den Einstellungen lief noch, oder keine gewählte Lampe war an |
| Lichtimpuls übersprungen: Meldung aus eigener Wirkung | Die Meldung hat eine Wirkung des Message Center selbst ausgelöst (ein Skript, eine Automation an einer geblinkten Lampe). Sie wird zugestellt, bekommt aber keinen Lichtimpuls, kein Alarmlicht und kein Skript, damit nichts im Kreis läuft |
| Lichtimpuls verweigert (kein Recht an den Lampen) | Die Lampen werden mit den Rechten dessen geschaltet, der die Meldung ausgelöst hat. Fehlt ihm das Recht, bleibt das Licht aus; der Push kommt trotzdem. Gilt auch für das Alarmlicht |
| Skript übersprungen (Meldung aus eigener Wirkung) | Wie oben: kein zweites Skript aus einer Meldung, die ein Skript ausgelöst hat |
| Skript fehlgeschlagen | Das Skript fehlt, hat einen Fehler oder brauchte länger als 30 Sekunden |
| jetzt gesendet | Jemand hat auf der Seite „Jetzt senden“ gedrückt |

**Wichtige Felder einer Meldungsart**

- **Nicht zurückhalten:** Die Meldung kommt auch bei aktiver Zustellregel sofort. Nötig für alles, was gerade *wegen* des Modus kommen soll, etwa „Fenster noch offen“ beim Einschalten des Nachtmodus.
- **Abstand:** Mindestzeit zwischen zwei vollen Meldungen derselben Sorte. Dazwischen wird nur der Zähler erhöht und der Push ersetzt, ohne Licht.
- **Verfall:** Eine noch nicht zugestellte Meldung wird nach dieser Zeit verworfen. Sinnvoll für alles, was morgens nicht mehr stimmt.

## Störungen

| Was auffällt | Ursache und Abhilfe |
|---|---|
| Eine Meldung kommt nicht an | Reiter „Offen“: Wartet sie? Dort steht der Grund (Regel, Abstand, zurückgestellt) und bis wann. Reiter „Verlauf“: verworfen oder verfallen? Reiter „Empfänger“: letzter Fehler des Handys. Ein Handy ohne Verbindung fällt dort meist nicht auf: Die App meldet so einen Fehler über ihren Push-Dienst nicht zurück (nur ein Gerät, das allein für Local Push eingerichtet ist, erscheint als Fehler) |
| Eine Meldung steht auf „wiederholen“, aber nichts passiert | Eine Zustellregel hält die Wiederholung zurück („zurückgehalten: ‹Regel› bis …“). Sie geht am Ende der Regel hinaus, oder sofort mit „Jetzt senden“ |
| Eine Meldung kommt trotz Nachtmodus | Die Meldungsart hat „Nicht zurückhalten“, oder es ist Stufe 3, oder die Regel hat ihre Höchstdauer überschritten (dann gibt es einen Reparaturhinweis) |
| Eine bekannte Meldung steht wieder unter „Neu“ | Der Titel wurde geändert, oder eine Automation ohne Titel wurde umbenannt; die Titelbedingung der Meldungsart anpassen oder „alle Meldungen dieser Automation“ wählen |
| Eine Meldungsart ist ausgegraut und „verwaist“ | Ihre Automation gibt es nicht mehr. Löschen; eine neue Meldungsart entsteht beim nächsten Bewerten |
| Antippen öffnet Home Assistant statt Message Center | Einstellung „Beim Antippen öffnen“ prüfen. Die Automation gibt selbst ein Ziel mit (`clickAction` oder `url`), oder das Handy gehört keinem Administrator |
| Die Regel wirkt nie | Der Schalter des Modus wird nicht geschaltet: Message Center schaltet ihn nie selbst. Eine Automation oder das Dashboard muss ihn ein- und ausschalten |
| Kein Lichtimpuls | Die Lampen müssen an sein (außer sie haben in der Lampenliste „auch wenn aus“), der Schalter „Lichtimpuls“ muss an sein, die Meldungsart darf nicht „nie“ sagen. Der Grund steht unter der Meldung (siehe Vermerke oben) |
| „Lichtimpuls verweigert“ oder kein Alarmlicht | Der Auslöser der Meldung darf die Lampen nicht schalten. Die Automation unter einem Nutzer mit Recht an den Lampen laufen lassen, oder die Lampen prüfen |
| Aktion `discard`, `snooze` oder `forward` abgelehnt („Unauthorized“) | Der Nutzer gehört zur Gruppe „Nur Lesen“ und darf das Message Center nicht steuern. Die Seite selbst steht ohnehin nur Administratoren offen |
| Reparaturhinweis „Empfänger nicht erreichbar“ | Home-Assistant-App auf dem Handy prüfen. Das Message Center versucht es 24 Stunden lang weiter |
| Reparaturhinweis „Regel kann Entität nicht lesen“ | Der Helfer oder die Integration hinter der Regel fehlt. Solange gilt die Regel als aktiv; die Höchstdauer beendet sie |
| Meldungen „unklar“ nach einem Neustart | Ob sie das Handy erreicht haben, ist nicht bekannt. Im Reiter „Offen“ „Jetzt senden“ oder „Verwerfen“ |
| „Nicht bereit“ im Kopf der Seite | Der Speicher lässt sich nicht schreiben. Reparaturhinweis lesen, Speicherplatz und Rechte von `.storage` prüfen. Sobald die Platte wieder schreibt, heilt sich das Message Center von selbst (spätestens nach 60 Sekunden); ein Neustart ist nicht nötig. Was in der Zeit fällig wird (Regelende, Wiederholung), wird trotzdem gesendet |
| Reparaturhinweis „Verlauf nicht schreibbar“ | Nur die Verlaufsdatei lässt sich nicht schreiben; Meldungen kommen weiter an. Platte und Rechte prüfen; der Hinweis verschwindet mit dem nächsten gelungenen Schreiben |
| Der Knopf auf dem Handy tut nichts | Das Handy erreicht Home Assistant gerade nicht. Oder, nur bei „Später“ und „An KI“: Der Nutzer, dem das Handy gehört, darf nur lesen oder ist deaktiviert (im Log `Push button … ignored: Unauthorized`) |
| Der Alarm ist leise | Einstellungen → Alarmkanal auf Android wechseln; auf dem iPhone „Kritische Hinweise“ für die App erlauben |

Reparaturhinweise stehen unter Einstellungen → System → Reparaturen. „Zugestellt“ heißt: an die App übergeben. Ob das Handy die Meldung wirklich gezeigt hat, kann das Message Center nicht sehen.
