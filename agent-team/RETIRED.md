# agent-team: retired 2026-10-09

**Status:** retired (stopped and disabled, not deleted). Nothing in this folder,
the config, or the runtime state was removed, so it can come back with a few
commands.

## Why

As of 2026-10-09 the Telegram agent-team bot is replaced by Rebecca's Grok Bot
assistants: **Morning Bot** (morning triage, vault inbox sweep, weekly review,
monthly archive), **Health Bot** (habit check-ins and health tracking) and
**Fun Bot** (culture and things-to-do digest). Running both duplicated work,
for example two inbox sweeps writing to `Reading/queue.md` and the daily note.

## What it did

- Ran a Telegram bot with Claude-powered literary personas (Jeeves, Bartleby,
  Gatsby, and others) for chat, planning, nudges and reminders.
- Captured clips (links and voice notes via local Whisper) into the Obsidian
  vault, and handled culture shortlist approvals.
- Read newsletter-digest data.
- Ran scheduled jobs: morning triage, habit check-in, weekly wins recap, and
  vault jobs (Gmail inbox sweep, tomorrow's daily note, Sunday AI radar,
  Sunday weekly review, monthly archive proposal).

## Where things live

| What | Location |
| --- | --- |
| Code | `~/Documents/GitHub/bexperiments/agent-team/` (this folder) |
| Live config (gitignored, holds secrets) | `agent-team/config.yaml` |
| Config backup at retirement | `~/.grok-staging/agent-team-config.yaml.2026-10-09-retired.bak` |
| LaunchAgent plist (still in place, disabled) | `~/Library/LaunchAgents/com.bexperiments.agent-team.plist` |
| Plist backup | `~/.grok-staging/com.bexperiments.agent-team.plist.2026-10-09.bak` |
| Runtime state, venv, launcher `run.sh` | `~/Library/Application Support/agent-team/` |
| Runtime state snapshot (no venvs or Whisper model) | `~/.grok-staging/agent-team-state-2026-10-09/` |
| Log | `~/Library/Logs/agent-team/bot.log` |

Every schedule in `config.yaml` was already set to `"off"` before retirement,
so restoring the bot brings back chat, clip capture and culture approvals
only. No scheduled job runs until you turn it back on.

## Restore

If `config.yaml` is missing, copy the backup back first:

```sh
cp ~/.grok-staging/agent-team-config.yaml.2026-10-09-retired.bak \
   ~/Documents/GitHub/bexperiments/agent-team/config.yaml
```

Then re-enable, load and start the LaunchAgent:

```sh
launchctl enable gui/$(id -u)/com.bexperiments.agent-team
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.bexperiments.agent-team.plist
launchctl kickstart -k gui/$(id -u)/com.bexperiments.agent-team
```

One line:

```sh
launchctl enable gui/$(id -u)/com.bexperiments.agent-team && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.bexperiments.agent-team.plist && launchctl kickstart -k gui/$(id -u)/com.bexperiments.agent-team
```

Check that it is back online with `tail -f ~/Library/Logs/agent-team/bot.log`.

To retire it again:

```sh
launchctl bootout gui/$(id -u)/com.bexperiments.agent-team
launchctl disable gui/$(id -u)/com.bexperiments.agent-team
```

## Turning individual scheduled jobs back on

Edit the `schedules:` block in `config.yaml`, replace `"off"` with the time,
then restart with `launchctl kickstart -k gui/$(id -u)/com.bexperiments.agent-team`.
These were the times before they were turned off (also listed in
`config.example.yaml`):

| Job | Old value | What it does | Now owned by |
| --- | --- | --- | --- |
| `morning_triage` | `"07:00"` | Jeeves: tasks and reminders agenda | Morning Bot (since 2026-10-07) |
| `habit_checkin` | `"21:00"` | Bartleby: today's habit-grid row | Grok Bot / Health Bot (since 2026-10-04) |
| `weekly_recap` | `"sun 19:00"` | Gatsby: weekly wins recap | Grok Bot (since 2026-10-04) |
| `vault_inbox_sweep` | `"06:45"` | Gmail sweep to `Reading/queue.md` and the daily note | Morning Bot |
| `vault_daily_notes` | `"23:55"` | Create tomorrow's daily note | No owner yet |
| `vault_ai_radar` | `"sun 17:30"` | Sunday AI radar proposals | **Intentionally dropped** |
| `vault_weekly_review` | `"sun 18:45"` | Sunday weekly review | Morning Bot |
| `vault_monthly_archive` | `"day1 20:00"` | Monthly archive proposal | Morning Bot |

The `vault_*` times are the code defaults in `vault_jobs.py`
(`DEFAULT_SCHEDULES`); `config.yaml` overrides them, so deleting a `vault_*`
line from `config.yaml` also restores its default time.

Before turning a job back on, make sure the Grok Bot assistant that now owns it
is turned off, or both will write to the vault.

**`vault_ai_radar` was intentionally dropped.** It was not moved to any Grok Bot
assistant. Leave it off unless you decide you want the Sunday AI radar back.
