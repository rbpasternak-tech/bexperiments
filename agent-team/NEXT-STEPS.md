# Agent Team — Next Steps

Update 2026-08-01 (later): fixed the "…" replies. A persona turn allowed
only 5 tool rounds; when a turn needed more (tool-error retries, or the
nightly check-in's read-today/read-yesterday/record-both flow), the loop
ended on a tool-use response with no text and the bot literally sent "…".
Turns now get 8 rounds, and on exhaustion the persona is forced into a
final plain-text wrap-up that relays tool errors verbatim; every tool call
and stop reason is logged to bot.log. NOTE: `git pull` does NOT restart
the launchd bot — re-run `./install-launchd.sh` (or
`launchctl kickstart -k gui/$(id -u)/com.bexperiments.agent-team`) after
pulling, or the old code keeps running.

Update 2026-08-01: fixed the month-rollover bug that broke habit reporting
on Aug 1 — nothing created `Tracking/Habits/2026-08.md`, so every
`record_habits` write failed with "Habit file not found" while the Apple
Health/MyFitnessPal export itself parsed fine. `upsert_habit_row` now
creates each new month's grid (columns copied from the previous month) and
inserts missing date rows. Health-export and vault errors now say exactly
what's wrong (folder missing vs. macOS/launchd permission denial vs.
undownloaded iCloud placeholder files) instead of a generic "not found".

Status 2026-07-27 (evening): **LIVE.** The Household Staff Bot
(t.me/HouseholdStaffBot) is running on Rebecca's Mac with its own BotFather
token; vault verified; Jeeves added a real task and Gatsby filed a To Try
item. Secrets (telegram_token, anthropic_api_key) live in the gitignored
agent-team/config.yaml — background processes don't read ~/.zshrc.

Remaining polish:
1. **Always-on**: launchd job so the bot survives Terminal closes/reboots
   (instructions given in chat; stop the manual run first — one poller only)
2. **health_export_dir**: set once the Health Auto Export automation is
   configured (app installed; automation: JSON, daily, iCloud, ~8:45pm)
3. **Cowork sweep tweak**: route non-URL self-sends to Tasks/Master.md
   (text given in chat 2026-07-27) so emailed to-dos hit the 7am triage
4. Watch the first scheduled runs land: 9pm check-in tonight, 7am triage,
   1pm pulse, 5:30pm capture, Sunday 7pm recap

## Architecture (settled)

**Cowork scheduled tasks are the scribes; the Telegram team is the voice.**
The three Cowork tasks (daily note create, inbox sweep, weekly review) keep
running and keep writing daily notes / queue sweeps / review sections. The
bot reads the vault directly (it's a plain folder on the Mac — no connector)
and only writes three things: habit-grid rows, Telegram reading captures,
and task checkboxes. One writer per note; no Gmail OAuth needed in the bot
because the inbox sweep already covers Gmail.

## Built and tested (offline, against a replica of the real vault)

- `vault.py` — read notes, capture to `Reading/queue.md` Inbox (URL-deduped,
  same conventions as the sweep), list/check tasks in `Tasks/Master.md`,
  fill `Tracking/Habits/YYYY-MM.md` grid rows in the exact table format
  (✅ / X / — cells, comma-formatted numbers, partial updates never clobber)
- `health_export.py` — parses Health Auto Export JSON: steps, calories
  (MyFitnessPal via Apple Health sync), weight
- `schedules.py` + duties in `main.py`: Jeeves 7:00 triage, Bartleby 21:00
  habit check-in, Gatsby Sunday 19:00 recap (after the weekly review runs)
- Persona prompts updated with duties; vault etiquette in shared rules
- Capture layer (added 2026-07-27): `list_vault_files` + append-only
  `append_to_note` — dictate daily-note sections (Worked on, People,
  Thinking about...) to Jeeves, To Try items (movies/restaurants/books) to
  Gatsby, project updates to any of them. Bartleby's nightly check-in now
  ends by offering to file reflections into today's note.

## Remaining setup (needs Rebecca, ~20 min)

1. **Run the bot** (README Setup): pull branch, install deps, copy
   `config.example.yaml` → `config.yaml`, token via
   `.claude/settings.local.json` or `TELEGRAM_BOT_TOKEN`, `python main.py`,
   `/whoami`, add chat id to `allowed_chat_ids`, restart.
2. **Point config at the vault**: set `vault_path` in `config.yaml` to the
   Second Brain folder under iCloud Obsidian documents.
3. **Health Auto Export** (iPhone):
   a. App Store → "Health Auto Export — JSON+CSV". Automations need Premium
      (small subscription or lifetime) — check price in-app first.
   b. Open app, grant Apple Health read access (Allow All).
   c. MyFitnessPal app → settings → enable Apple Health sync (writes
      calories into Health so one export covers nutrition).
   d. In the app: Automations → new automation → format JSON, aggregation
      Daily, metrics: Steps + Dietary Energy + Weight/Body Mass →
      destination iCloud Drive (its own folder) → schedule daily ~8:45pm
      (just before Bartleby's 9pm check-in).
   e. Set `health_export_dir` in `config.yaml` to that folder (visible in
      Finder under iCloud Drive → Health Auto Export).
   f. No Premium / not sure? Skip — Bartleby still asks nightly and fills
      the grid from your one-line answer; numbers just stay manual.
4. **Optional Cowork prompt tweak** (Claude drafted it in chat 2026-07-27):
   make the inbox sweep route non-URL self-sends into `Tasks/Master.md` as
   task candidates, so emailed to-dos reach Jeeves' morning triage.
5. **First live test**: message the bot; ask Bennet to capture a link; say
   "done 1" to Jeeves after triage; wait for the 9pm check-in.

## Later

- Always-on: launchd job or a `tmux-bexperiments.sh` window for `main.py`
- Vault Q&A ("what did I say about X?") — needs a search tool over the vault
- Need-to-read triage flow for the queue's organic sections
