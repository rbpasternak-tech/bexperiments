# Agent Team — Next Steps

Pickup plan. Read top to bottom tomorrow; tell Claude "work through
agent-team/NEXT-STEPS.md" to resume where we left off.

## Where things stand (2026-07-26)

Built and pushed on branch `claude/plan-mode-w2mq4s`:

- One Telegram bot, four classic-literature personas (Jeeves 🎩 chief of
  staff, Elizabeth Bennet 📖 accountability, Gatsby 🥂 celebration,
  Bartleby 🖋️ deadpan nudges) — voices live in `personas.yaml`
- Haiku router picks who answers; or address by name ("Jeeves, ...")
- Shared per-chat memory; timed reminders (set/list/cancel via tool use);
  reads the latest trends-dashboard digest
- Offline-tested (routing, reminders, history, digest reader). Not yet run
  live against Telegram — that needs your token, which only exists on your Mac.

Note on the old bot: `telegram_bot.py` was never committed — `.gitignore`
line 22 excludes it by name, so it exists only on your Mac. Nothing was
lost; it was always local-only. The new `agent-team/` Telegram layer was
therefore written from scratch (and is committed, since it contains no
secrets).

## Step 1 — Get it running on your Mac (~10 min)

1. `git pull` and check out `claude/plan-mode-w2mq4s` (or merge it to main)
2. `cd agent-team && pip install -r requirements.txt`
3. `cp config.example.yaml config.yaml`
4. Token: reuse the bot token from your existing local Telegram setup —
   put it in `.claude/settings.local.json` as
   `{"env": {"TELEGRAM_BOT_TOKEN": "..."}}` (the file is gitignored), or
   export `TELEGRAM_BOT_TOKEN`. If you'd rather keep the old bot separate,
   make a fresh bot with @BotFather. `ANTHROPIC_API_KEY` must also be set.
5. `python main.py`, message the bot `/whoami`, put the chat id into
   `allowed_chat_ids` in `config.yaml`, restart. Say hello to Jeeves.

## Step 2 — What to commit vs. keep local

- Commit: everything in `agent-team/` except `config.yaml` (gitignored —
  it holds your chat id). Persona edits in `personas.yaml` are safe to commit.
- Never commit: the bot token, `.claude/settings.local.json`,
  `.claude/telegram-state/` (conversation history + reminders — gitignored).
- Optional: if the old `telegram_bot.py` has logic worth keeping, rename a
  cleaned copy (no token inside) into a project folder so it's in git;
  otherwise retire it.
- Reminder: this repo is public via GitHub Pages — assume anything
  committed is public.

## Step 3 — Duties interview (Claude interviews you)

The personas currently have voices but generic duties. Tomorrow, have
Claude interview you about real pain points, then encode the answers into
`personas.yaml` roles/prompts and new tools. Questions to expect:

1. What falls through the cracks weekly? (bills, follow-ups, appointments,
   job-search tasks, habits?)
2. What does a good morning look like — should Jeeves send a daily brief
   (calendar + reminders + digest) at a set time?
3. What do you procrastinate on that Bartleby/Lizzy should pester you
   about, and how aggressively?
4. What's calendar-driven vs. habit-driven vs. inbox-driven?
5. What should the bot never do without asking (send email, move events)?
6. Which persona should own which duty?

Output of the interview: a duties table per persona + a list of new tools
to build.

## Step 4 — Connectors the duties will need

The bot is a standalone Python process, so it needs its own credentials —
claude.ai connectors don't carry over to it. Likely wiring, in order of
probable usefulness:

- Google Calendar: reuse the OAuth pattern from
  `newsletter-digest/gmail_client.py`; add the Calendar scope and a
  `get_todays_events` tool. (Same Google Cloud project as Gmail can work.)
- Gmail read-only: "any newsletters/important mail today?" — again reuse
  `gmail_client.py`.
- Habit tracker: habit data lives in browser localStorage, so the bot
  can't read it directly. Options: export habits to a JSON file the bot
  reads, or have habit-tracker sync to a file/endpoint. Decide tomorrow.
- Scheduled proactive messages (morning brief): either a due-time entry the
  polling loop checks (like reminders — no new infra), or launchd.
- Note: in Claude sessions (not the bot), Gmail/Calendar/Drive connectors
  are already available — useful for prototyping duties before wiring the
  bot's own credentials.

## Step 5 — Keeping it always-on (later)

The bot only responds while `python main.py` runs. Options when ready:
launchd job on the Mac (KeepAlive), or a tmux window added to
`tmux-bexperiments.sh`. Decide after duties are settled.

## Suggested order tomorrow

1. Step 1 (run it, 10 min) → confirm personas answer in Telegram
2. Step 3 interview → rewrite duties in `personas.yaml`
3. Pick the one connector that unblocks the most duties (likely Calendar)
   and build its tool
4. Commit + push; leave Steps 4-remainder and 5 for the day after
