---
name: hitprint
description: Find a creator's "hitprint" — the measurable traits their best short videos share. Use when the user says "find my hitprint", "what do my best videos have in common", "analyze my channel", or "analyze my shorts".
---

# Hitprint

Runs locally. Needs `ffmpeg`, `yt-dlp`, and (optional) `whisper` on PATH.

## Steps

1. Work out the source:
   - YouTube: a handle (`@name`) or a channel URL (`https://www.youtube.com/channel/UC…`).
   - Any other platform: a folder of the user's video files plus a stats export.
   - If the user has a YouTube Studio export, add `--studio FILE` (scores by stayed-to-watch).
2. Run the CLI (it can take several minutes; downloads are cached in `OUT/cache`):
   ```bash
   hitprint @name                              # or a channel URL
   hitprint --folder ./videos --stats export.csv
   ```
   Options: `--out DIR` (default `./hitprint-out`), `--cookies-from-browser chrome` if YouTube shows a bot check, `--no-whisper` to skip the first-word check.
   - Exit code 2 means fewer than 10 usable videos: tell the user, don't retry.
   - A bot-check error: rerun with `--cookies-from-browser chrome`.
3. In chat, summarize from the CLI output (or `hitprint-out/hitprint-data.json`):
   - The top rules, each with its sample size ("based on 14 vs 12 videos").
   - The 3 next fixes (the fixable rules).
   - Say these are patterns from their own videos, not proof. Never claim causation.
4. Offer to open the report (`hitprint-out/hitprint-report.html`), and mention `my-formula.md` can be pasted into a script-writing prompt.
