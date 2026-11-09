# Translation lookups

Fast terminal dictionary lookups through dict.cc using ordinary HTTP requests.
No API key or browser process is required.

```sh
ten relativieren        # German -> English (also the default direction)
fen house               # English -> German
tfr Haus                # German -> French
ffr maison              # French -> German
tit Haus                # German -> Italian
fit casa                # Italian -> German
translate ten "eine Aussage relativieren"
translate --loop fen
translate -l fen house  # include word-class labels where available
translate -m 20 ten relativieren
```

Compact output shows up to six entries, preserving dict.cc's order. `-m` changes
the limit; `-l` includes labels and shows up to 999 entries by default.

A confirmed empty lookup prints `No translations found for 'word' on dict.cc.`
and succeeds with exit status 0. Network/HTTP errors, crawler blocks (including
blocks returned with HTTP 200), and unrecognized page layouts are reported on
stderr with exit status 1. The interactive loop continues after missing words
or request failures. Queries are sent as URL parameters and are not executed as
JavaScript; translations are extracted from the HTML result rows.
