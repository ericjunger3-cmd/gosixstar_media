# Instagram-Posting ohne Claude

Die Reels werden von GitHub Actions gepostet, nicht mehr aus einer Claude-Sitzung.
Damit ist das Veröffentlichen unabhängig von Usage-Limits und Ausfällen.

## Wie es läuft

1. Die Produktion legt das fertige Reel in `reels/` ab und trägt es in `reels/queue.json` ein.
2. `post.yml` läuft alle 10 Minuten, postet alles Fällige und schreibt `posted_at`,
   `media_id` und `permalink` zurück.
3. `cleanup.yml` löscht ein Reel drei Stunden nachdem es live gegangen ist.
4. `token_check.yml` prüft montags, ob der Zugang noch funktioniert.

Ein ausgefallener Lauf verzögert einen Post höchstens um zehn Minuten; gepostet wird
jeder Eintrag genau einmal. Liegt ein Eintrag mehr als sechs Stunden hinter seiner Zeit,
wird er übersprungen und ein Issue geöffnet, damit nachts nichts Altes rausgeht.

## Was einmalig einzurichten ist

Zwei Repository-Secrets unter Settings - Secrets and variables - Actions:

| Secret | Wert |
|---|---|
| `IG_USER_ID` | `17841453956595537` (die Instagram-Business-ID von @gosixstar) |
| `IG_ACCESS_TOKEN` | Zugriffstoken mit der Berechtigung zum Veröffentlichen |

Das Token holst du dir bei developers.facebook.com: App-Dashboard - Instagram -
"API setup with Instagram business login" - bei @gosixstar auf "Generate token".
Das Token gilt 60 Tage und lässt sich danach verlängern.

Nötige Berechtigungen: Veröffentlichen (`instagram_content_publish` bzw.
`instagram_business_content_publish`) und Kommentare (`instagram_manage_comments`) -
ohne die zweite kommt das Reel raus, aber der erste Kommentar nicht.

Kommt das Token aus "Instagram business login", lege zusätzlich unter Settings -
Secrets and variables - Actions - Variables eine Variable `IG_API_BASE` mit dem Wert
`https://graph.instagram.com/v21.0` an. Bei einem Token über Facebook-Login kannst du
sie weglassen.

Trag die Werte selbst ein - sie gehören nicht in einen Chat und nicht in eine Datei
im Repository.

Danach: Actions - "Check the Instagram token" - Run workflow. Läuft der grün durch,
stimmt alles.

## Format von queue.json

```json
[
 {"id": "mw06",
  "file": "ig_mw06_boobie.mp4",
  "cover": "SixStar_Thumb_mw06.jpg",
  "caption": "Streets to empire ...\n\n#gta6 #gtavi",
  "comment": "Would you sign with him? SIGN or NAH",
  "post_at": "2026-11-14T14:00:00Z"}
]
```

`cover` und `comment` sind optional. `post_at` ist UTC.
Felder, die der Workflow selbst schreibt: `posted_at`, `media_id`, `permalink`,
`tries`, `last_error`, `gave_up`.

## Von Hand auslösen

Actions - "Post due reels to Instagram" - Run workflow. Mit `dry_run: 1` zeigt er nur,
was er posten würde.
