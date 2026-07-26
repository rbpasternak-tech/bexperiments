"""Telegram agent team: a cast of sitcom personas that help run your life.

One bot, four Parks and Recreation personas. Address a teammate by name
("Ron, remind me to lift at 6") or just talk — a router picks who answers.
Personas share one chat transcript, can set/cancel reminders, and can pull
the latest newsletter-digest trends.

Run: python main.py   (long-polls Telegram; Ctrl-C to stop)
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
import yaml

from persona_agent import run_persona_turn
from router import build_alias_map, pick_persona
from schedules import Scheduler
from state import StateStore
from telegram_api import TelegramClient, load_token
from vault import Vault

PROJECT_DIR = Path(__file__).resolve().parent

SCHEDULED_DUTIES = {
    "morning_triage": (
        "jeeves",
        "It is the scheduled morning triage. Call get_open_tasks and "
        "list_reminders. Present a brief numbered agenda for the day: open "
        "tasks first (note anything that looks long-stale), then today's "
        "reminders. If both are empty, say so in one line. The user can "
        "reply 'done <n>' or ask you to snooze/cancel items.",
    ),
    "habit_checkin": (
        "bartleby",
        "It is the scheduled nightly habit check-in. First call "
        "read_health_export for today. Then ask the user, in one dry line, "
        "for today's manual habits: rings, floss, vibe plate, red light, "
        "leg roller, read (audio), read (physical), and weight if measured. "
        "Mention any numbers the export already gave you. When they answer, "
        "you will record everything with record_habits.",
    ),
    "weekly_recap": (
        "gatsby",
        "It is the scheduled Sunday recap. Read this month's habit file "
        "(Tracking/Habits/<current YYYY-MM>.md) and today's daily note "
        "(Daily/<today>.md) via read_vault_note. Toast the week's genuine "
        "wins — streaks, finished tasks, anything from the weekly review "
        "section — in a few charming sentences. No fabricated wins.",
    ),
}

HELP_TEXT = """Your team:
{roster}

Talk normally and the right teammate answers, or address one directly:
  "Leslie, plan my morning"  ·  "@ron remind me to lift at 6pm"

Commands:
  /team — who's on the team
  /reminders — pending reminders
  /whoami — this chat's id (for the config allowlist)
  /help — this message"""


def load_config():
    """Load config.yaml (falling back to config.example.yaml) and personas.yaml."""
    config_path = PROJECT_DIR / "config.yaml"
    if not config_path.exists():
        config_path = PROJECT_DIR / "config.example.yaml"
        print("Note: config.yaml not found, using config.example.yaml defaults.")
    config = yaml.safe_load(config_path.read_text())
    personas_cfg = yaml.safe_load((PROJECT_DIR / "personas.yaml").read_text())
    return config, personas_cfg


def make_roster_text(personas_cfg):
    """Render the team roster as plain text for /team and /help."""
    return "\n".join(
        f"{p['emoji']} {p['name']} — {p['role'].strip()}"
        for p in personas_cfg["personas"].values()
    )


def handle_command(text, chat_id, personas_cfg, state, telegram):
    """Handle slash commands. Returns True if the message was a command."""
    command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    if command in ("/start", "/help"):
        telegram.send_message(
            chat_id, HELP_TEXT.format(roster=make_roster_text(personas_cfg))
        )
    elif command == "/team":
        telegram.send_message(chat_id, make_roster_text(personas_cfg))
    elif command == "/whoami":
        telegram.send_message(
            chat_id,
            f"This chat's id is {chat_id}. Add it to allowed_chat_ids in "
            "agent-team/config.yaml.",
        )
    elif command == "/reminders":
        reminders = state.list_reminders(chat_id)
        if not reminders:
            telegram.send_message(chat_id, "No pending reminders.")
        else:
            lines = [
                f"{r['due']} — {r['text']} (id {r['id']}, via {r['persona']})"
                for r in reminders
            ]
            telegram.send_message(chat_id, "\n".join(lines))
    else:
        return False
    return True


def handle_message(message, config, personas_cfg, alias_map, claude, ctx, telegram):
    """Route one incoming Telegram message to a persona and send the reply."""
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    state = ctx["state"]
    if not text:
        return
    allowed = config.get("allowed_chat_ids") or []
    if chat_id not in allowed:
        telegram.send_message(
            chat_id,
            f"This chat isn't authorized yet. Chat id: {chat_id} — add it to "
            "allowed_chat_ids in agent-team/config.yaml and restart the bot.",
        )
        return
    if handle_command(text, chat_id, personas_cfg, state, telegram):
        return
    history = state.get_history(chat_id)
    persona_key, persona_text = pick_persona(
        claude, config["router_model"], personas_cfg, alias_map, text, history
    )
    state.append_history(chat_id, "user", text)
    persona = personas_cfg["personas"][persona_key]
    try:
        reply = run_persona_turn(
            claude, config["model"], persona_key, personas_cfg, persona_text,
            dict(ctx, chat_id=chat_id),
        )
    except anthropic.APIError as exc:
        telegram.send_message(chat_id, f"({persona['name']} is unavailable: {exc})")
        return
    state.append_history(chat_id, persona["name"], reply)
    telegram.send_message(chat_id, f"{persona['emoji']} {persona['name']}:\n{reply}")


def run_scheduled_duties(scheduler, config, personas_cfg, claude, ctx, telegram):
    """Fire any due scheduled duties into the first allowed chat."""
    allowed = config.get("allowed_chat_ids") or []
    if not allowed:
        return
    chat_id = allowed[0]
    state = ctx["state"]
    for key in scheduler.due_schedules():
        persona_key, instruction = SCHEDULED_DUTIES.get(key, (None, None))
        if not persona_key or persona_key not in personas_cfg["personas"]:
            print(f"Warning: schedule {key!r} has no matching duty/persona.")
            continue
        persona = personas_cfg["personas"][persona_key]
        try:
            reply = run_persona_turn(
                claude, config["model"], persona_key, personas_cfg, instruction,
                dict(ctx, chat_id=chat_id),
            )
        except anthropic.APIError as exc:
            print(f"Scheduled duty {key} failed: {exc}", file=sys.stderr)
            continue
        state.append_history(chat_id, persona["name"], reply)
        telegram.send_message(chat_id, f"{persona['emoji']} {persona['name']}:\n{reply}")


def deliver_due_reminders(personas_cfg, state, telegram):
    """Send any reminders whose due time has passed."""
    for reminder in state.pop_due_reminders():
        persona = personas_cfg["personas"].get(
            reminder["persona"], next(iter(personas_cfg["personas"].values()))
        )
        telegram.send_message(
            reminder["chat_id"],
            f"⏰ {persona['emoji']} {persona['name']}: {reminder['text']}",
        )
        state.append_history(
            reminder["chat_id"], persona["name"], f"(reminder) {reminder['text']}"
        )


def main():
    """Start the long-polling loop."""
    parser = argparse.ArgumentParser(description="Telegram persona team bot")
    parser.add_argument(
        "--once", action="store_true",
        help="poll a single batch of updates and exit (for testing)",
    )
    args = parser.parse_args()

    config, personas_cfg = load_config()
    alias_map = build_alias_map(personas_cfg)
    telegram = TelegramClient(load_token())
    claude = anthropic.Anthropic()
    state = StateStore(history_limit=config.get("history_limit", 40))
    vault = Vault(config.get("vault_path"))
    scheduler = Scheduler(state, config.get("schedules"))
    ctx = {
        "state": state,
        "vault": vault,
        "health_export_dir": config.get("health_export_dir"),
    }

    vault_note = "vault OK" if vault.available() else "vault NOT found (tools degrade)"
    print(f"Agent team online ({', '.join(personas_cfg['personas'])}); {vault_note}.")
    offset = 0
    while True:
        try:
            updates = telegram.get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(
                        update["message"], config, personas_cfg, alias_map,
                        claude, ctx, telegram,
                    )
            deliver_due_reminders(personas_cfg, state, telegram)
            run_scheduled_duties(scheduler, config, personas_cfg, claude, ctx, telegram)
        except KeyboardInterrupt:
            print("\nBye.")
            sys.exit(0)
        except Exception as exc:
            print(f"[{datetime.now():%H:%M:%S}] error: {exc}", file=sys.stderr)
            time.sleep(5)
        if args.once:
            break


if __name__ == "__main__":
    main()
