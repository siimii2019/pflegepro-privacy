# Scola – Redesign-Entwurf

Lokaler Entwurf für die Website der privaten Sekundarstufe Scola. **Nicht die offizielle Website**, nur lokal gedacht.

## Lokaler Start

Im Ordner `scola-entwurf`:

```
python3 -m http.server 8000
```
oder `npx serve`. Aufruf: http://localhost:8000

## Technik

Reines HTML, CSS und rund 50 Zeilen JavaScript. Kein Build-Schritt, kein Vite: Bei acht Seiten bringt ein Build-Tool mehr Aufwand als Nutzen. Schriften (Fraunces für Überschriften, Nunito Sans für Text, beide SIL OFL) liegen lokal in `assets/fonts`. Keine Cookies, kein Tracking, keine externen Aufrufe. Alle Seiten sind `noindex`.

## Platzhalter (gelb markiert, in eckigen Klammern)

- Adresse, Telefon, E-Mail (Angaben von der bestehenden Website, nicht bestätigt)
- Termine: Tag der offenen Tür, Schnuppertage, Anmeldefrist
- Zeiten und Inhalte des Schultags
- Hüther-Zitat: Wortlaut und Quelle
- Schulgeld, Betreuungszeiten, Gruppengrößen, Öffentlichkeitsrecht und Abschlüsse
- Team: Namen, Funktionen, Fotos
- Aktuelles: Beiträge; FAQ-Antworten
- Impressum und Datenschutz (komplett; rechtlich verbindlich von der Schule)
- Social-Links Facebook und Instagram, Copyright-Zeile
- Alle Fotos (SVG-Platzhalter mit Maßangabe)

## Offene Fragen

1. Bleibt die Anmeldung ein Formular? Wohin sollen die Daten (E-Mail, Tool)? Das Formular sendet aktuell nichts.
2. Gibt es ein Logo und Fotos? Der Entwurf nutzt ein Platzhalter-Logo.
3. Eigene Seite für die Cookie-Richtlinie oder ein Abschnitt in der Datenschutzerklärung?
4. Open-Graph-Bilder fehlen bewusst (kein Bild vorhanden).
