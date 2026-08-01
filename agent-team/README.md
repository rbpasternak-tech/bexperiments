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
folder (`health_export_dir`). On the first write of a new month the bot
creates `Tracking/Habits/YYYY-MM.md` itself, copying the previous month's
table columns, so the grid rolls over without manual setup. Scheduled duties run on the polling loop:
Jeeves' 7am task triage, Bartleby's 9pm habit check-in, Gatsby's Sunday
recap (times configurable under `schedules`).

The team is also a frictionless capture layer for the vault: dictate from
your phone and it files things append-only into the right place — "worked
on X" / "talked to Sarah" / "thinking about Y" into today's daily-note
sections (Jeeves), movies/restaurants/books into the To Try lists (Gatsby),
updates under project notes. Bartleby's nightly check-in ends by asking if
anything belongs in today's note.

Division of labor with other vault automations: all bot writes are
append-only (grid cells, queue captures, checkboxes, dictated lines).
Auto-generated sections (Sweep flags, Weekly review) and note creation
belong to their own scheduled tasks — the bot never rewrites content.

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
- `health_export.py` — parses Health Auto Export JSON (steps/calories/weight)
- `schedules.py` — recurring duties (7am triage, 9pm check-in, Sunday recap)
- `personas.yaml` — the cast: voices, roles, aliases (edit to recast the show)
- `state.py` — JSON persistence in `.claude/telegram-state/` (gitignored)
- `telegram_api.py` — minimal Telegram Bot API wrapper (no SDK)
