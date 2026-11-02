# Hitprint — design spec
*2 Nov 2026 · status: approved (name: Hitprint — "the fingerprint of your hits")*

Related project seen in the name check: `nalediym/creator-dna` reads what a person *watches* on TikTok and suggests topics; it does not measure your own posted videos against your own numbers, so Hitprint is distinct.

## 1. Goal
Give any short-form creator **their own winning formula**: what their best videos have in common, measured from their own videos and their own numbers. The tool must be:
- free and open source
- local
- installable with one command
- usable from any AI coding tool (Claude Code, Codex, Antigravity, Cursor) or a plain terminal.

**Who it's for:** YouTubers and short-form creators.

**What success looks like:**
- A creator gets a readable report with 3 concrete fixes within minutes of installing.
- We can show it working live on our own 31 Shorts.
- It's published on GitHub.

**New-ness check (done 2 Nov 2026, public GitHub plus a web search):**
- Viral-video analyzers, outlier finders and hook-text writers already exist.
- A general Shorts research project exists, written in German.
- Nothing found that builds a creator's *personal* rules from their *own* videos. We say "we couldn't find anything like it", never "world's first".

## 2. What the creator does
| Input | Command |
|---|---|
| YouTube (automatic) | `hitprint @handle`, or tell the AI "find my hitprint @handle" |
| Any platform (TikTok, Reels, etc.) | `hitprint --folder ./my-videos --stats tiktok_export.csv` |
| Optional upgrade | `--studio studio_export.csv`, which adds YouTube Studio's "stayed to watch" (a better signal than views) |

**Output:** `hitprint-report.html` (opens automatically), `my-formula.md` (paste into any AI when scripting the next video), and `hitprint-data.json`.

## 3. How it works (5 parts, one file each)
1. **`collect`** gets the list of videos plus their numbers.
   - **YouTube:** all Shorts from the public channel via yt-dlp (views, likes, length, title, upload date). No login.
   - **Folder mode:** the creator's own video files, plus a stats file in one of three formats: a TikTok Studio export, a Meta Business Suite / Instagram Professional Dashboard export, or our simple template (`file, views[, stayed_pct]`).
     - Files are matched to stats rows by file name first, then by upload date and length.
     - Files that can't be matched are listed in the report, not guessed.
   - **Skipped:** videos younger than 3 days, because their views haven't settled.
2. **`fetch`** (YouTube only) downloads a small 360p copy of each Short into a local cache.
   - Downloads are spaced out to avoid YouTube's bot check.
   - The cache means a second run is fast.
   - Optional `--cookies-from-browser` if YouTube still blocks.
3. **`measure`** extracts features per video.
   - **Editing features** (the Shorts Doctor measurements): seconds to first spoken word (Whisper), time of first cut, longest shot, cuts per 10 seconds, loudness (LUFS), first-frame brightness, loop match, and length.
   - **Title and caption features:** length, says "you", is a question, has a number, has an emoji, and series prefix (e.g. "What if YOU were").
   - **Upload weekday and hour.**
4. **`analyze`** finds the creator's rules.
   - **Performance score:** views, or stayed-to-watch when a Studio export is given.
   - **Grouping:** each feature splits the videos into two groups.
     - Numeric features split at the median, or at a meaningful threshold such as "first cut under 1s".
     - Yes/no features split by yes and no.
   - **Comparison:** the median score of the two groups.
   - **What counts as a rule:** both groups need **at least 5 videos**, and the difference must be **1.3× or more**.
   - **Ranking:** rules are ranked by effect size × confidence, using a simple bootstrap check that the gap isn't luck.
   - **Wording:** every rule states its sample size, for example "based on 14 vs 12 videos".
5. **`report`** writes three files.
   - **HTML report** (dark, the same style as Shorts Doctor):
     - "Your formula": the top 5 rules in plain English.
     - "Your next 3 fixes": the biggest effect the creator can still change.
     - Best vs. worst: first-second filmstrips of the top 3 and bottom 3 videos.
     - A full table of every video with every measurement.
     - A "patterns, not proof" note.
   - **`my-formula.md`:** the same rules, written as instructions for an AI scriptwriter.
   - **`hitprint-data.json`:** all the raw numbers.

**Packaging:**
- A plain Python CLI using only the standard library, with ffmpeg, yt-dlp and whisper as the only outside tools.
- A `SKILL.md` so Claude Code, Codex and other agents can drive it.
- Installs with `npx skills add <owner>/hitprint`.

## 4. Error handling
- **Fewer than 10 usable videos:** stop with a clear message ("need at least 10 Shorts").
- **A video fails to download or measure:** skip it, keep going, and list it in the report with the reason.
- **YouTube's bot check:** back off and retry 3 times, then suggest `--cookies-from-browser`.
- **Whisper missing:** run without the first-word check and say so in the report.
- **No rule passes the 5-video / 1.3× bar:** say so honestly ("no clear patterns yet — keep posting") rather than inventing rules.

## 5. Testing
- **Unit tests:** the stats matcher, the grouping and threshold logic, and rule ranking, all with small fixtures.
- **Real run on our channel (31 Shorts):**
  - Spot-check 3 videos' measurements by hand against Shorts Doctor.
  - Check the rules make sense against what we already know (the monster video is our top performer; our weaker Shorts have long uncut shots).
- **Folder-mode run:** 10+ of our local videos plus a template CSV, standing in for TikTok and Reels.
- **Second-agent check:** run the skill from Codex or Antigravity once, to prove it works outside Claude Code.

## 6. Production plan (video + GitHub)
1. **Recording setup:**
   - VS Code full screen, with the Claude app hidden before recording starts.
   - The demo script starts the recording and types each prompt.
   - The user starts it with one command and clicks "allow" on permission prompts.
   - *Lesson from tutorial 3: the chat window must not be on top.*
2. **Build sessions (recorded), 4 prompts, each a chapter of the video:**
   1. Build the YouTube version.
   2. Run it on our channel.
   3. Add any-platform folder mode.
   4. Polish the report and add `my-formula.md`.
3. **Proof:**
   - Show our real results.
   - Apply the #1 fix to one new Short, if time allows. If it isn't done, we don't claim results.
4. **GitHub:**
   - A public repo under the user's account (SOULGPT): README with screenshots, MIT license, one-line install.
   - Published **only after the user approves** the final version.
5. **Video:**
   - Main tutorial, 16:9, about 3–4 min. Hook: "I found the hitprint of all 31 of my Shorts. Here's what my best ones have in common."
   - Steps, with build moments from the session log.
   - Our real formula, then a call to action ("run it and comment your #1 rule").
   - 2 Shorts cut from it.
   - Narration in the narrator voice (ref_a). The altered-content label is ticked.

## 7. Out of scope for v1
- Automatic TikTok or Instagram scraping (both need a login and break often).
- Long-form videos.
- A web app.
- Thumbnail analysis.
- Competitor channels (the tool is for your own channel).
