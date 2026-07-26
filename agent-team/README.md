# Agent Team

A team of AI agents in your Telegram, cast as Parks and Recreation characters,
who help run your life. One bot token, four personas:

- 📋 **Leslie Knope** — chief of staff: planning, scheduling, pep talks
- 🥩 **Ron Swanson** — blunt accountability and scope-cutting
- 🕶️ **Tom Haverford** — fun, breaks, and Treat Yo Self logistics
- 🖤 **April Ludgate** — deadpan nudges and reminders

Talk normally and a router (Claude Haiku) picks who answers, or address a
teammate directly: `Ron, remind me to lift at 6pm`. All personas share one
chat transcript, so they know what the others said. They can set, list, and
cancel timed reminders, and pull the latest topics from the
[newsletter digest](../newsletter-digest/) trends data.

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

## Usage

- `/team` — roster
- `/reminders` — pending reminders
- `/help` — commands and examples
- `Leslie, plan my morning` · `@april did I do my habits?` · `what's in the news?`

Reminders fire on the bot's polling loop (roughly ±30s precision), delivered
in the voice of whichever persona set them.

## Files

- `main.py` — entry point: long-polling loop, commands, reminder delivery
- `router.py` — direct-address matching + Haiku-based persona routing
- `persona_agent.py` — Claude call with tool-use loop per persona turn
- `agent_tools.py` — reminder + digest tools the personas can call
- `personas.yaml` — the cast: voices, roles, aliases (edit to recast the show)
- `state.py` — JSON persistence in `.claude/telegram-state/` (gitignored)
- `telegram_api.py` — minimal Telegram Bot API wrapper (no SDK)
