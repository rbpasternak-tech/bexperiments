# Agent Team: How the System Works

A standalone description of the Telegram agent team and how it feeds the
Obsidian Second Brain. Written so it can be handed to another system (or
another AI) as context.

---

## 1. What it is, in one paragraph

A single Python process running on a Mac (kept alive by `launchd`) talks to
one Telegram bot. Behind that bot are four AI personas, each cast as a
classic-literature character with a job. Rebecca messages the bot from her
phone; a router decides which persona answers; that persona calls Claude
with a set of tools that can read and append to the Obsidian vault, set
reminders, read Apple Health data, and pull newsletter trends. On a
schedule the same process also runs "duties" (morning triage, nightly habit
check-in, etc.) and unattended "Second Brain jobs" (inbox sweep, weekly
review, monthly archive proposal). Everything written to the vault is
append-only.

```
 iPhone (Telegram) ─────────────┐
                                ▼
                  ┌───────────────────────────┐
 Apple Health ──► │  Agent Team bot (main.py) │ ◄── launchd keeps it running
 (Health Auto     │  long-poll loop           │
  Export files)   │   ├─ router (Haiku)       │
 MyFitnessPal ──► │   ├─ persona turn (Sonnet │
 Gmail (read) ──► │   │   + tools)            │
 Newsletter    ─► │   ├─ reminders            │
 digest data      │   ├─ scheduled duties     │
                  │   ├─ Second Brain jobs    │
                  │   └─ hourly health import │
                  └────────────┬──────────────┘
                               │ append-only writes
                               ▼
                    Obsidian vault (iCloud folder)
          Daily/ · Tasks/Master.md · Reading/queue.md ·
          Tracking/Habits/YYYY-MM.md · To Try lists · Projects/
```

---

## 2. The cast

One bot token, four personas, defined in `personas.yaml` (voice, role,
aliases). Recasting the show means editing that file.

| Persona | Voice | Job | Owns |
|---|---|---|---|
| 🎩 **Jeeves** (Wodehouse), default | Unflappable valet | Chief of staff: planning, scheduling, reminders | Morning triage, evening capture, daily-note captures, project updates, completing tasks |
| 📖 **Elizabeth Bennet** (Austen) | Witty, candid | Accountability, cutting scope | Midday pulse, reading ledger (`capture_reading`) |
| 🥂 **Jay Gatsby** (Fitzgerald) | Lavish, "old sport" | Celebration, breaks, rewards | To Try lists (movies, restaurants, books), Sunday wins recap |
| 🖋️ **Bartleby** (Melville) | Deadpan, "would prefer not to" | Nudges and habit pestering | 9pm habit check-in, habit grid |

All personas share **one chat transcript** (last ~40 entries), so each
knows what the others said.

---

## 3. What happens when a message arrives

1. **Poll.** `main.py` long-polls the Telegram Bot API (no SDK, just
   `telegram_api.py`).
2. **Authorize.** Only chat ids in `allowed_chat_ids` are served. Others get
   their chat id back so it can be added (`/whoami`).
3. **Commands.** `/team`, `/reminders`, `/help`, `/whoami`, and
   `/run sweep|review|archive|notes` are handled directly without an AI call.
4. **Route** (`router.py`):
   - *Direct address wins*: `Jeeves, plan my morning` or `@bartleby ...`
     matches an alias and goes straight to that persona.
   - *Otherwise* a small, cheap model (Claude Haiku) gets the roster plus the
     last 6 transcript lines and answers with one persona key. It keeps the
     last speaker if the message continues their thread. Any error falls
     back to Jeeves.
5. **Persona turn** (`persona_agent.py`):
   - System prompt = persona's character prompt + shared ground rules
     (plain text for Telegram, keep it short, use tools instead of
     pretending, vault etiquette, give a one-line filing receipt) + current
     date/time + the shared transcript.
   - Calls the main model (Claude Sonnet) with the tool list. Runs up to
     **8 tool rounds**. Tool errors come back to the model as text rather
     than crashing the turn.
   - If the turn ends with no text (out of tokens or out of rounds), a
     forced text-only "wrap-up" call summarizes what was done and relays
     errors verbatim.
6. **Reply.** Sent to Telegram as `🎩 Jeeves:\n<reply>` and appended to the
   shared transcript.

After each poll batch the loop also delivers due reminders and fires any
due scheduled duties or jobs.

### Persona tools (`agent_tools.py`)

| Tool | What it does |
|---|---|
| `set_reminder` / `list_reminders` / `cancel_reminder` | Timed reminders stored in the state dir; delivered in the setting persona's voice (±30s) |
| `get_latest_digest` | Top topics from the newsletter digest (`trends-dashboard/data/`) |
| `read_vault_note` | Read any vault note |
| `list_vault_files` | List notes in a vault folder |
| `append_to_note` | Append a line under a section heading (daily-note sections, To Try lists, project notes, `Tasks/Master.md`) |
| `capture_reading` | Add a link to the reading queue Inbox |
| `get_open_tasks` / `complete_task` | Read unchecked tasks in `Tasks/Master.md`; tick one off |
| `read_health_export` | Steps, calories, weight, ring verdict for a date |
| `record_habits` | Fill cells in the month's habit grid row |

---

## 4. How it feeds Obsidian

The vault is an iCloud-synced folder that the bot reads and writes
directly as plain markdown (`vault.py`). There is no Obsidian plugin or API
involved.

### Vault layout the bot relies on

| Path | Purpose | Who writes |
|---|---|---|
| `Daily/YYYY-MM-DD.md` | Daily note, created from `Templates/Daily.md` | Bot creates missing notes; personas append to sections; jobs add auto sections |
| `Tasks/Master.md` | Master task list (`- [ ]` checkboxes) | Personas append new tasks and tick completed ones |
| `Reading/queue.md` | Reading queue with an Inbox | `capture_reading`; inbox sweep adds dated subsections |
| `Tracking/Habits/YYYY-MM.md` | Monthly habit grid (markdown table, one row per day) | Health import + Bartleby's check-in |
| To Try lists (movies, restaurants, books…) | Things to try | Gatsby |
| `Projects/<name>/index.md` | Project notes | Personas append updates (never create a project without confirming) |
| `README.md`, `ABOUT.md` | Vault conventions | Read-only; jobs read these first |

### The write rules

- **Append-only.** Every bot write adds: a table cell, a queue line, a
  checkbox tick, a line under a heading, or a new auto section. It never
  rewrites existing content.
- **Hand edits win.** The health import only fills an empty cell or one it
  wrote itself last time.
- **Auto-generated sections belong to their job.** Personas never touch
  `Sweep flags`, `Weekly review`, or `Monthly archive proposal` sections.
- **Jobs have a code-enforced allowlist** (`vault_jobs.py`):
  - inbox sweep: may add queue items and a `Sweep flags` section
  - weekly review: may add a `Weekly review` section
  - monthly archive: may add a `Monthly archive proposal` section
  - sections may only be added to `Daily/` notes
- **Idempotent.** Re-running a job never duplicates a section; the queue
  skips URLs already present.
- **Receipts.** After filing, personas reply with one line like
  `Filed: plumber → Tasks; Sinners → To Try/Movies` so misfiles can be
  redirected.
- **Rollover.** On the first write of a new month the bot creates
  `Tracking/Habits/YYYY-MM.md`, copying last month's columns.
- **iCloud eviction.** If a file was evicted to the cloud, the bot asks
  `brctl` to download it and retries.

### Capture flow (dictation → vault)

| Rebecca says | Goes to |
|---|---|
| "Worked on X", "talked to Sarah", "thinking about Y" | Matching section of today's daily note (Jeeves) |
| "Need to call the plumber" | `- [ ] ...` in `Tasks/Master.md` |
| A link / article | `Reading/queue.md` Inbox (Lizzy) |
| A movie, restaurant, book | The right To Try list (Gatsby) |
| A project update | Under that project's note |
| "done 3" | Ticks task 3 from the morning agenda |
| Habit answers at 9pm | Today's row in the habit grid (Bartleby) |

---

## 5. The daily rhythm

Scheduled duties are persona turns started by the bot, sent to the first
allowed chat. Times are local and configurable in `config.yaml` under
`schedules` (`"HH:MM"`, `"sun HH:MM"`, `"day1 HH:MM"`, or `off`).

| Time | What | Persona / job | Vault effect |
|---|---|---|---|
| 06:45 | **Inbox sweep** | Job | New Gmail items in `Reading/queue.md`; `Sweep flags` in today's note |
| 07:00 | **Morning triage** | Jeeves | Reads yesterday + today; posts what's new, a numbered agenda (tasks + reminders), then asks for new captures |
| 13:00 | **Midday pulse** | Lizzy | Asks what landed; files tasks, people, links, to-try items |
| 17:30 | **Evening capture** | Jeeves | Asks for worked on / people / tasks / tomorrow; files into today's note |
| 21:00 | **Habit check-in** | Bartleby | Refreshes health import, fills the last 4 days' missing numbers, asks only for habits the export can't know (floss, vibe plate, red light, leg roller, read audio/physical), then offers to add to today's note |
| 23:55 | **Daily notes** | Job (no AI) | Creates missing `Daily/` notes through tomorrow |
| Sun 18:45 | **Weekly review** | Job | `Weekly review (auto-generated …)` section in today's note |
| Sun 19:00 | **Weekly recap** | Gatsby | Toasts real wins from the habit grid and weekly review; no invented wins |
| 1st, 20:00 | **Monthly archive** | Job | `Monthly archive proposal` checklist in today's note. Proposal only: nothing is moved |

Before any duty that touches daily notes, the bot makes sure yesterday's
and today's notes exist. At morning triage, `cowork_watch.py` posts one
alert if a note had to be backfilled, the Gmail sweep is over a day old,
or (on Mondays) Sunday's weekly review is missing.

**Catch-up after sleep.** Fired slots are recorded in the state dir. If the
Mac was asleep, missed slots fire on the next poll: same day for daily
duties, up to three days for weekly and monthly jobs.

---

## 6. Second Brain jobs (unattended)

These used to be Cowork scheduled tasks. They moved into the bot because
Cowork skips any slot the Mac sleeps through. Each job:

1. Loads its instructions from `vault_jobs/<job>.md`.
2. Gets a small tool set: `read_note`, `list_files`, `last_gmail_sweep`,
   `gmail_search`, `gmail_read`, `add_queue_items`, `append_section`.
3. Works for up to 40 rounds, with writes limited by the allowlist.
4. Posts its final summary (or failure) to Telegram as `🗂 <Job>: ...`.

Run one on demand with `/run sweep`, `/run review`, `/run archive`, or
`/run notes`.

**Inbox sweep details.** Rebecca emails herself links from her phone and
leaves articles unread as "read later". The sweep:
- Works out its lookback from the newest `Gmail sweep (date)` header in the
  queue (1–14 days, so a missed day heals itself).
- Searches `from:me to:me newer_than:Nd` and `is:unread newer_than:Nd`
  (read-only Gmail).
- Keeps real reading, drops promo and transactional mail, one entry per URL:
  `- [ ] **Title** — URL _(saved YYYY-MM-DD, self-send|unread)_ (summary)`
- Scans yesterday's daily note for stray URLs.
- Flags (does not act on) people, tasks, projects, and time-sensitive items
  in today's `Sweep flags` section.

**Weekly review** reads the last 7 daily notes, the reading queue,
`Tasks/Master.md` and the habit grid, then writes coverage, work done,
habit counts, inbox themes, stale tasks, and suggested promotions. It ends
with "Reply with edits/approvals and I'll execute."

**Monthly archive** flags dormant projects, ideas untouched for 60+ days,
and queue items older than 90 days as a checklist. Nothing moves until
Rebecca replies.

---

## 7. Health data pipeline

```
Apple Watch/iPhone ─► Health Auto Export app ─► iCloud folder (.hae / JSON)
                                                     │
MyFitnessPal (optional, calories) ──────────────────►│
                                                     ▼
                     health_import.py (hourly + before 9pm)
                                                     │
                                                     ▼
                         Tracking/Habits/YYYY-MM.md row
                     Steps · Calories · Weight · Rings · …
```

- Runs on a background thread every `health_import_every_minutes` (60)
  and once more right before the check-in.
- Looks back 7 days and never writes today, because today's totals are
  still growing.
- Writes partial days and upgrades them when the final totals arrive.
- The Rings column is judged automatically against `ring_goals`
  (move kcal, exercise minutes, stand hours).
- Calorie gaps can be backfilled from MyFitnessPal, which runs in its own
  venv. Any failure there returns "no data" and never breaks the import.
- A ledger (`health-import.json`) tracks what was written. `doctor.sh`
  prints the last run.

---

## 8. Other inputs

- **Newsletter digest.** A separate project (`newsletter-digest/`) writes
  trend JSON to `trends-dashboard/data/`. The personas read the newest one
  via `get_latest_digest` ("what's in the news?").
- **Gmail.** Read-only, used only by the inbox sweep. It uses a copy of the
  newsletter digest's OAuth token, placed in the state dir by
  `install-launchd.sh`.

---

## 9. Runtime and operations

| Thing | Where / how |
|---|---|
| Entry point | `agent-team/main.py` (`--once` polls a single batch for testing) |
| Process manager | launchd agent `com.bexperiments.agent-team` (`RunAtLoad`, `KeepAlive`), installed by `install-launchd.sh` |
| State (history, reminders, fired slots, health ledger, Gmail token) | `~/Library/Application Support/agent-team/`. Kept outside the repo because iCloud eviction crash-looped launchd |
| Config | `agent-team/config.yaml` (gitignored; template `config.example.yaml`) |
| Secrets | `telegram_token` and `anthropic_api_key` in config, or env vars `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY` |
| Models | `model` (personas and jobs, Sonnet) and `router_model` (Haiku) |
| Health check | `./doctor.sh`: code version, exactly one poller (two causes Telegram 409), launchd, paths, health parse, habit grid, log tail |
| Updating | `git pull` does **not** restart the bot. Re-run `./install-launchd.sh` afterwards |
| Logs | `bot.log`, including every tool call and its stop reason |

### Key config keys

```yaml
model: claude-sonnet-5
router_model: claude-haiku-4-5-20251001
allowed_chat_ids: [123456789]        # first id receives scheduled duties
vault_path: "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<Vault>"
health_export_dir: "~/Library/Mobile Documents/iCloud~com~HealthExport~HealthAutoExport/Documents"
health_import_every_minutes: 60
ring_goals: { move_kcal: 500, exercise_min: 30, stand_hours: 12 }
schedules:
  morning_triage: "07:00"
  midday_pulse: "13:00"
  evening_capture: "17:30"
  habit_checkin: "21:00"
  weekly_recap: "sun 19:00"
  # Second Brain jobs default to on; set to "off" to disable
  vault_inbox_sweep: "06:45"
  vault_weekly_review: "sun 18:45"
  vault_monthly_archive: "day1 20:00"
  vault_daily_notes: "23:55"
history_limit: 40
```

---

## 10. Design principles, summarized

1. **One chat, many voices.** Personas make different jobs easy to address
   and easy to tell apart. A shared transcript keeps them coherent.
2. **Cheap routing, capable answering.** Haiku picks the persona; Sonnet
   does the work.
3. **Capture should be frictionless.** Dictate anything and the right
   persona files it, then sends a one-line receipt.
4. **The vault is sacred.** Writes are append-only and idempotent, hand
   edits win, jobs are allowlisted in code, and structural changes are
   proposed, never made.
5. **Survive the laptop.** launchd keeps it alive, missed slots catch up,
   state lives outside iCloud, and evicted files are re-downloaded.
6. **Fail loudly but narrowly.** Tool errors cost one tool result, not the
   turn. Job failures post to Telegram. Optional integrations fail to
   "no data".

## File map

| File | Role |
|---|---|
| `main.py` | Poll loop, commands, duties, reminders, job dispatch |
| `router.py` | Direct-address match + Haiku routing |
| `persona_agent.py` | One persona turn with a tool loop and wrap-up |
| `agent_tools.py` | Persona tool definitions and handlers |
| `personas.yaml` | The cast |
| `vault.py` | Vault read/append helpers, habit grid, daily-note creation |
| `vault_jobs.py` + `vault_jobs/*.md` | Unattended Second Brain jobs and their instructions |
| `schedules.py` | Slot parsing, fired-state tracking, catch-up |
| `health_export.py` / `health_import.py` | Health Auto Export parsing; hourly grid import |
| `mfp_source.py`, `mfp_fetch.py`, `mfp_login.py` | Optional MyFitnessPal calorie backfill |
| `gmail_reader.py` | Read-only Gmail for the sweep |
| `cowork_watch.py` | Morning alerts for missed notes, sweeps, or reviews |
| `state.py` | JSON persistence (history, reminders, fired slots) |
| `telegram_api.py` | Minimal Bot API wrapper |
| `install-launchd.sh`, `run.sh`, `doctor.sh` | Install, run, diagnose |
