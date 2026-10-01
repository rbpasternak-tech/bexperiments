# Agent Team

A team of AI agents in your Telegram, cast as classic literature characters,
who help run your life. One bot token, four personas:

- 🎩 **Jeeves** (Wodehouse) — chief of staff: planning, scheduling, discreet fixes
- 📖 **Elizabeth Bennet** (Austen) — witty accountability and scope-cutting
- 🥂 **Jay Gatsby** (Fitzgerald) — celebration, breaks, and rewards, old sport
- 🖋️ **Bartleby** (Melville) — deadpan nudges he would prefer not to send

Talk normally and a router (Claude Haiku) picks who answers, or address a
teammate directly: `Jeeves, remind me to lift at 6pm`. All personas share one
chat transcript, so they know what the others said. They can set, list, and
cancel timed reminders, and pull the latest topics from the
[newsletter digest](../newsletter-digest/) trends data.

When an Obsidian vault is configured (`vault_path` in config.yaml) the team
also works your second brain: reading notes, capturing links to the reading
queue, checking off tasks in `Tasks/Master.md`, and filling the monthly
habit grid — with steps/calories/weight pulled from a Health Auto Export
folder (`health_export_dir`), and the Rings column auto-judged against
your `ring_goals` when the automation also exports Active Energy,
Exercise Time, and Stand Hours. On the first write of a new month the bot
creates `Tracking/Habits/YYYY-MM.md` itself, copying the previous month's
table columns, so the grid rolls over without manual setup.

Health numbers fill in automatically: a background import runs hourly
(`health_import_every_minutes`) and again before the 9pm check-in, writing
each recent past day's steps, calories, weight, and rings as soon as the
phone's AutoSync push lands. A day whose final totals haven't arrived yet
is written with its partial numbers and upgraded later. The import never
overwrites a cell you edited by hand, and a read failure for yesterday is
reported in Telegram at the check-in. `doctor.sh` shows its last run.

Scheduled duties run on the polling loop:
Jeeves' 7am task triage, Bartleby's 9pm habit check-in, Gatsby's Sunday
recap (times configurable under `schedules`).

The 7am triage is the one daily message, in four parts: what's new since
yesterday, a **Work desk** (Inbox, Littler intel, Legal tech news), the
agenda, and a capture question. The Work desk only reuses existing output
(`work_desk.py`): today's 6:45 sweep flags and queue subsection, the newest
self-sent "Daily AI Competitive Intelligence" email (one targeted read-only
Gmail search), and the newsletter digest's JSON in `trends-dashboard/data`.
Each source is classified NEW / NONE TODAY / STALE / UNAVAILABLE in code
(a Littler issue whose body date trails delivery by more than a day is
STALE; a digest slot in its launchd plist with no run is flagged
LATE/MISSED), so old issues are never reposted. It writes nothing to the
vault. Preview without sending or writing: `python main.py --preview-triage`.

The team is also a frictionless capture layer for the vault: dictate from
your phone and it files things append-only into the right place — "worked
on X" / "talked to Sarah" / "thinking about Y" into today's daily-note
sections (Jeeves), movies/restaurants/books into the To Try lists (Gatsby),
updates under project notes. Bartleby's nightly check-in ends by asking if
anything belongs in today's note.

Division of labor with other vault automations: bot writes are
append-only (grid cells, queue captures, checkboxes, dictated lines, new
clip notes and project folders) with two deliberate exceptions the weekly
jobs own: the review's queue cleanup (archive + theme promotion) and the
AI radar note, which is rebuilt each week.

## Clips: reels, videos and articles become notes

Share a link from your phone to the bot (Instagram reel, TikTok, YouTube
Short, X/Facebook video, or any article), with an optional note about why.
The bot fetches it with yt-dlp, transcribes the audio **on the Mac** with
faster-whisper (nothing is sent to a transcription service), extracts
article text with trafilatura, asks Claude for a title, summary, key
claims and tags, and writes one note per item to `Reading/clips/
<date> <title>.md` — frontmatter plus the full transcript or article
text, so the vault holds what the thing actually said. A one-line pointer
goes into today's daily note. Sending a video file (or voice note) works
the same way. Duplicate URLs are skipped.

When a fetch fails (Instagram often refuses without a login; paywalls),
the bot asks you to paste the caption or what it said and files that
instead — or reply `skip`. `clips.cookies_from_browser: safari` in
config.yaml lets yt-dlp use your browser login for Instagram.

### AI radar (Sunday 17:30)

`vault_ai_radar` reads every clip note, the reading queue and its archive,
your project notes and the week's daily notes, then rewrites
`Ideas/AI radar.md`: recurring themes with trend and evidence links, what
changed this week, the five queue items most worth reading, and three
ranked project proposals grounded in what you saved (why now, evidence,
first step). The week's proposals are also appended to today's daily note
as an append-only history, and posted to Telegram. Reply `yes 2` and the
bot creates `Projects/<title>/index.md` from your Project template with the
proposal filled in. `/run radar` runs it on demand.

### Weekly review now acts

The Sunday review no longer only proposes: before the model turn it moves
Inbox subsections older than 30 days to `Archive/Reading queue archive.md`
(the queue's own retention rule), and the model promotes items that share
a theme into `## Theme` sections of the queue with `promote_queue_items`.
Its daily-note section also names the top five reads for the week.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and grab the token.
2. Put the token in `.claude/settings.local.json` at the repo root:
   ```json
   { "env": { "TELEGRAM_BOT_TOKEN": "123456:ABC..." } }
   ```
   (or export `TELEGRAM_BOT_TOKEN` in your shell).
3. Make sure `ANTHROPIC_API_KEY` is set (same as newsletter-digest).
4. `pip install -r requirements.txt`
5. `cp config.example.yaml config.yaml`
6. Run `python main.py`, message your bot `/whoami`, and add the printed chat
   id to `allowed_chat_ids` in `config.yaml`. Restart.

## Troubleshooting

Run `./doctor.sh` in this folder. It checks the checked-out code version,
that exactly one bot process is polling (two causes Telegram 409 and a
silent bot), the launchd job, config paths, a live health-export parse for
today and yesterday, the month's habit grid, and tails `bot.log` — each as
a PASS/WARN/FAIL line. Remember: `git pull` does not restart the bot;
re-run `./install-launchd.sh` after updating.

## Usage

- `/team` — roster
- `/reminders` — pending reminders
- `/help` — commands and examples
- `Jeeves, plan my morning` · `@bartleby did I do my habits?` · `what's in the news?`

Reminders fire on the bot's polling loop (roughly ±30s precision), delivered
in the voice of whichever persona set them.

## Files

- `main.py` — entry point: long-polling loop, commands, reminders, schedules
- `router.py` — direct-address matching + Haiku-based persona routing
- `persona_agent.py` — Claude call with tool-use loop per persona turn
- `agent_tools.py` — reminder, digest, vault, and health tools
- `vault.py` — Obsidian vault read/write (queue, tasks, habit grid)
- `health_export.py` — reads Health Auto Export data (AutoSync `.hae` files and JSON exports)
- `health_import.py` — hourly background import of health numbers into the habit grid
- `clips.py` — fetch a link's content: yt-dlp download + local Whisper transcript, or article text
- `clip_ingest.py` — summarize a capture and write the clip note (+ caption fallback, Telegram receipt)
- `ai_radar.py` — weekly synthesis note, project proposals, and "yes N" project creation
- `schedules.py` — recurring duties (7am triage, 9pm check-in, Sunday recap)
- `personas.yaml` — the cast: voices, roles, aliases (edit to recast the show)
- `state.py` — JSON persistence in `~/Library/Application Support/agent-team/` (outside the repo and iCloud)
- `telegram_api.py` — minimal Telegram Bot API wrapper (no SDK)

## Second Brain jobs (formerly Cowork scheduled tasks)

The vault jobs that used to be Cowork scheduled tasks now run inside the bot
(`vault_jobs.py`, instructions in `vault_jobs/`). Cowork tasks skip any slot
the Mac sleeps through; the bot runs under launchd and its scheduler catches
up missed slots as soon as the Mac wakes (same day for daily jobs, up to
three days for weekly and monthly ones).

| Job | Default slot | Writes |
|---|---|---|
| `vault_daily_notes` | 23:55 | Missing `Daily/` notes through tomorrow, from `Templates/Daily.md` |
| `vault_inbox_sweep` | 06:45 (before the 07:00 triage) | New subsection in `Reading/queue.md` Inbox; `## Sweep flags` in today's note |
| `vault_ai_radar` | sun 17:30 | Rewrites `Ideas/AI radar.md`; `## AI radar (auto-generated …)` in today's note |
| `vault_weekly_review` | sun 18:45 | Archives 30-day-old Inbox subsections, promotes themed items into `## Theme` queue sections, `## Weekly review (auto-generated …)` in today's note |
| `vault_monthly_archive` | day1 20:00 | `## Monthly archive proposal (…)` in today's note — proposal only |

Each job's summary (or failure) is posted to Telegram. Run one on demand by
sending `/run sweep`, `/run review`, `/run archive`, `/run notes`, or `/run radar`. Writes are enforced
in code, append-only and idempotent (a re-run never duplicates a section).
Override a slot or disable a job with `off` under `schedules:` in
`config.yaml`. The inbox sweep reads Gmail read-only with a copy of the
newsletter digest's token, which `install-launchd.sh` places in
`~/Library/Application Support/agent-team/gmail_token.json`.

The duties that read or write daily notes also create any missing ones, and
at the morning triage `cowork_watch.py` posts one alert if a daily note had
to be backfilled, the Gmail sweep is more than a day old, or (Mondays)
Sunday's weekly review is missing.

Vault reads that hit an iCloud-evicted file (EDEADLK) ask `brctl` to
download it and retry.
