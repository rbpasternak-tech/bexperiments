"""Telegram agent team: a cast of literary personas that help run your life.

One bot, four classic-literature personas (see personas.yaml). Address a
teammate by name ("Jeeves, remind me to lift at 6") or just talk — a router
picks who answers.
Personas share one chat transcript, can set/cancel reminders, and can pull
the latest newsletter-digest trends. A shared link or video skips the
personas: it is fetched, transcribed locally, summarized and filed as a clip
note in the vault (clip_ingest.py), and "yes N" starts a project proposed
by the weekly AI radar (ai_radar.py).

Run: python main.py   (long-polls Telegram; Ctrl-C to stop)
"""

import argparse
import sys
import time
import traceback
from datetime import datetime, date
from pathlib import Path

import anthropic
import yaml

from health_import import (
    DEFAULT_EVERY_MINUTES,
    import_recent_days,
    start_background_import,
)
import ai_radar
import culture_shortlist
import clip_ingest
from clips import MEDIA_TMP_DIR, find_urls
from cowork_watch import cowork_warnings, format_alert
from gmail_reader import GmailReader
from persona_agent import run_persona_turn
import vault_jobs
from router import build_alias_map, pick_persona
from schedules import Scheduler
from state import StateStore
from telegram_api import TelegramClient, load_secret, load_token
from work_desk import build_work_desk
from vault import Vault

PROJECT_DIR = Path(__file__).resolve().parent

SCHEDULED_DUTIES = {
    "morning_triage": (
        "jeeves",
        "It is the scheduled morning triage — the user's one daily message; "
        "deliver it in four parts. "
        "PART 1 — What's new since yesterday: read yesterday's and today's "
        "daily notes, clip notes "
        "in Reading/clips/ whose filename starts with yesterday's or today's "
        "date (list_vault_files), any Inbox section of Tasks/Master.md, and "
        "yesterday's row in this month's habit file. Summarize the genuinely "
        "new items in a few bullets (clips by title, "
        "new tasks, habit row filled or not); "
        "skip the section entirely if nothing is new. Leave Gmail and the "
        "reading-queue sweep to Part 2. "
        "PART 2 — Work desk: exactly three short labelled lines, in this "
        "order — Inbox, Littler intel, Legal tech news — built ONLY from the "
        "WORK DESK FACTS block at the end of this instruction (do not search "
        "Gmail, the web, or the digest yourself, and do not borrow items "
        "from other notes or briefings). Inbox: what today's sweep added, "
        "then at most three of ITS flags that need the user's judgment or "
        "carry a date; if the facts say NONE TODAY, that one line is the "
        "whole Inbox entry. Littler intel and Legal tech news: when the facts say "
        "NEW, give at most three one-line highlights; when they say NONE "
        "TODAY, STALE or UNAVAILABLE, say so in one line with the reason "
        "and never repeat items from an older issue; always pass on a "
        "LATE/MISSED note. "
        "PART 3 — The agenda: call get_open_tasks and list_reminders and "
        "present a brief numbered agenda (flag long-stale tasks). "
        "PART 4 — Close with one inviting question: anything new to "
        "capture — tasks, ideas, things to do, see, watch, or try? When "
        "the user answers, file every item (tasks to Tasks/Master.md, "
        "to-try items to the To Try lists, ideas to today's daily note, "
        "links via capture_reading) — EXCEPT new projects: never create a "
        "project yourself; confirm its name and intended home first. The "
        "user can also reply 'done <n>' or snooze/cancel items.",
    ),
    "midday_pulse": (
        "lizzy",
        "It is the scheduled midday pulse. Ask the user, in one or two "
        "pointed sentences, what has landed since morning: new tasks worth "
        "tracking, people they have spoken to, links worth keeping, "
        "anything they want to try. When they answer, file every item with "
        "your tools: tasks as '- [ ] ...' lines appended to Tasks/Master.md "
        "under the best-fitting section, people and notes into today's "
        "daily-note sections, links via capture_reading, to-try items to "
        "the To Try lists. If they say nothing's new, accept it in one dry "
        "sentence and move on.",
    ),
    "evening_capture": (
        "jeeves",
        "It is the scheduled end-of-day capture. Ask the user for the day's "
        "record before it evaporates: what they worked on, whom they spoke "
        "to, any new tasks, anything on their mind for tomorrow. Keep it to "
        "one courteous question, not a form. When they answer, file each "
        "item into the matching section of today's daily note "
        "(Worked on, People I talked to, Thinking about, Tomorrow) via "
        "append_to_note, and add new tasks as '- [ ] ...' lines to "
        "Tasks/Master.md. Confirm in one line what was filed where.",
    ),
    "habit_checkin": (
        "bartleby",
        "It is the scheduled nightly habit check-in. Health numbers for "
        "past days are imported into the grid automatically (hourly), so "
        "do not re-record days that already have Steps. First read this "
        "month's habit file (Tracking/Habits/<YYYY-MM>.md) and note "
        "which of the THREE days BEFORE today (yesterday back) still have "
        "an empty Steps cell. For each such day call read_health_export and "
        "record what it returns with record_habits AGAINST THE DATE IT "
        "BELONGS TO — steps, calories, weight, and the rings yes/no "
        "verdict when present; a finished day's numbers usually arrive "
        "the morning after, so yesterday's numbers go in yesterday's "
        "row, never today's. Never call read_health_export for today: "
        "today's export does not exist until tomorrow, so an empty "
        "today row is expected, not missing data. Skip a day whose "
        "result is flagged "
        "'partial' unless its row would otherwise stay empty. Then ask "
        "the user, in one dry "
        "line, ONLY for the habits the export did not cover: floss, vibe "
        "plate, red light, leg roller, read (audio), read (physical) — "
        "plus rings only if the export had no rings verdict, and weight "
        "only if it had no weight. Note which day's numbers you already "
        "filed. When they answer, record their answers with record_habits "
        "for today (their word beats the export if they correct a rings "
        "call). After that, ask one flat "
        "follow-up: anything for today's note — worked on, people, "
        "thinking about. If they offer something, file each item into the "
        "matching section of today's daily note via append_to_note; if "
        "they decline, drop it without comment.",
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
  "Jeeves, plan my morning"  ·  "@bartleby remind me to lift at 6pm"

Share a link (reel, TikTok, YouTube, article) or send a video, with an
optional note, and it is transcribed and filed as a note in Reading/clips/.
The Sunday AI radar proposes projects from everything saved; reply
"yes 2" to create proposal 2 in Projects/.

Commands:
  /team — who's on the team
  /reminders — pending reminders
  /run sweep | review | archive | notes | radar — run a Second Brain job now
  /whoami — this chat's id (for the config allowlist)
  /help — this message"""

PENDING_CAPTION_HOURS = 6


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
    media = _video_attachment(message)
    if not text and not media:
        return
    allowed = config.get("allowed_chat_ids") or []
    if chat_id not in allowed:
        telegram.send_message(
            chat_id,
            f"This chat isn't authorized yet. Chat id: {chat_id} — add it to "
            "allowed_chat_ids in agent-team/config.yaml and restart the bot.",
        )
        return
    if media:
        handle_video_capture(media, message, config, claude, ctx, telegram, chat_id)
        return
    if text.lower().split()[0] == "/run":
        run_job_command(text, config, claude, ctx, telegram, chat_id)
        return
    if handle_command(text, chat_id, personas_cfg, state, telegram):
        return
    # A reply to a pending NYC Culture Shortlist ("add 1 and 3", "add all",
    # "none") is consumed here so it never reaches the persona router.
    if culture_shortlist.handle_reply(text, ctx, telegram, chat_id):
        return
    if handle_capture(text, config, claude, ctx, telegram, chat_id):
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
    except Exception as exc:
        traceback.print_exc()
        telegram.send_message(
            chat_id,
            f"({persona['name']} hit an error: {type(exc).__name__}: {exc})",
        )
        return
    state.append_history(chat_id, persona["name"], reply)
    telegram.send_message(chat_id, f"{persona['emoji']} {persona['name']}:\n{reply}")


def _video_attachment(message):
    """Return (file_id, filename) for a video sent to the chat, else None."""
    for key in ("video", "video_note", "animation"):
        if message.get(key):
            return message[key]["file_id"], message[key].get("file_name") or f"{key}.mp4"
    document = message.get("document") or {}
    if (document.get("mime_type") or "").startswith(("video/", "audio/")):
        return document["file_id"], document.get("file_name") or "attachment"
    if message.get("voice"):
        return message["voice"]["file_id"], "voice.ogg"
    return None


def handle_video_capture(media, message, config, claude, ctx, telegram, chat_id):
    """Download a video/voice message and file it as a clip note."""
    file_id, filename = media
    note = (message.get("caption") or "").strip()
    urls = find_urls(note)
    try:
        path = telegram.download_file(file_id, MEDIA_TMP_DIR / f"tg-{message.get('message_id', 0)}")
    except Exception as exc:
        telegram.send_message(chat_id, f"📎 Couldn't download that file: {exc}")
        return
    telegram.send_message(chat_id, f"📎 Got the video ({filename}) — transcribing…")
    state = ctx["state"]
    state.append_history(chat_id, "user", f"(sent a video{': ' + note if note else ''})")
    clip_ingest.run_capture_async(
        ctx, claude, config["model"], telegram, chat_id,
        url=urls[0] if urls else None, note=note, video_path=str(path),
    )


def handle_capture(text, config, claude, ctx, telegram, chat_id):
    """Handle shares, caption replies and 'yes N'. True when consumed.

    A message that is a URL plus at most a short note is a share: it is
    filed in the background. A plain message after a failed fetch is the
    caption Rebecca was asked for. 'yes N' creates radar proposal N.
    """
    state = ctx["state"]
    pending_key = f"pending_clip:{chat_id}"
    if clip_ingest.looks_like_capture(text):
        urls = find_urls(text)
        note = text
        for url in urls:
            note = note.replace(url, " ")
        state.set_value(pending_key, None)
        state.append_history(chat_id, "user", text)
        telegram.send_message(
            chat_id, f"📎 Got it — fetching{' and transcribing' if urls else ''}…"
        )
        for url in urls[:3]:
            clip_ingest.run_capture_async(
                ctx, claude, config["model"], telegram, chat_id,
                url=url, note=" ".join(note.split()),
            )
        return True
    pending = state.get_value(pending_key)
    if pending:
        try:
            age_h = (datetime.now() - datetime.fromisoformat(pending["asked_at"])).total_seconds() / 3600
        except (KeyError, ValueError):
            age_h = PENDING_CAPTION_HOURS + 1
        if age_h > PENDING_CAPTION_HOURS:
            state.set_value(pending_key, None)
        elif text.lower().strip(" .!") in ("skip", "drop", "never mind", "nevermind", "forget it"):
            state.set_value(pending_key, None)
            telegram.send_message(chat_id, f"📎 Dropped {pending['url']}.")
            return True
        else:
            state.set_value(pending_key, None)
            state.append_history(chat_id, "user", f"(caption for {pending['url']}) {text}")
            telegram.send_message(chat_id, "📎 Thanks — filing that…")
            clip_ingest.run_capture_async(
                ctx, claude, config["model"], telegram, chat_id,
                url=pending["url"], note=pending.get("note", ""), caption=text,
            )
            return True
    chosen = ai_radar.match_yes(text, state)
    if chosen:
        index, proposal = chosen
        result = ai_radar.create_project_from_proposal(ctx["vault"], proposal)
        if result.startswith("Error") or result.startswith("Vault not"):
            reply = f"Couldn't create proposal {index}: {result}"
        else:
            reply = (f"🗂 Created {result} for \"{proposal['title']}\". "
                     f"First step: {proposal['first_step']}")
        state.append_history(chat_id, "user", text)
        state.append_history(chat_id, "Radar", reply)
        telegram.send_message(chat_id, reply)
        return True
    return False


def run_scheduled_duties(scheduler, config, personas_cfg, claude, ctx, telegram):
    """Fire any due scheduled duties into the first allowed chat."""
    allowed = config.get("allowed_chat_ids") or []
    if not allowed:
        return
    chat_id = allowed[0]
    state = ctx["state"]
    for key in scheduler.due_schedules():
        if key.startswith("vault_"):
            run_vault_job(key, config, claude, ctx, telegram, chat_id)
            continue
        persona_key, instruction = SCHEDULED_DUTIES.get(key, (None, None))
        if not persona_key or persona_key not in personas_cfg["personas"]:
            print(f"Warning: schedule {key!r} has no matching duty/persona.")
            continue
        persona = personas_cfg["personas"][persona_key]
        # The background thread imports health numbers hourly; run it once
        # more right before the check-in so the persona sees a fresh grid,
        # and surface a read failure here (at most once a night) rather
        # than from the hourly thread.
        # Daily notes are made by a Cowork task that stops when the Mac
        # sleeps. Make sure yesterday's and today's exist before any duty
        # that reads or writes them, and say so when Cowork missed a run.
        if key in ("morning_triage", "evening_capture", "habit_checkin"):
            created = ctx["vault"].ensure_daily_notes(date.today())
            if created:
                print(f"[{key}] created daily notes: {', '.join(created)}", flush=True)
            if key == "morning_triage":
                alert = format_alert(cowork_warnings(ctx["vault"], date.today(), created))
                if alert:
                    print(f"[{key}] {alert}", flush=True)
                    telegram.send_message(chat_id, alert)
        if key == "habit_checkin":
            result = import_recent_days(ctx)
            print(f"[habit_checkin] health import: {result['summary']}", flush=True)
            if result["error"]:
                telegram.send_message(chat_id, f"⚠️ Health import: {result['summary']}")
        if key == "morning_triage":
            instruction = triage_instruction(ctx)
        try:
            reply = run_persona_turn(
                claude, config["model"], persona_key, personas_cfg, instruction,
                dict(ctx, chat_id=chat_id),
            )
        except Exception as exc:
            traceback.print_exc()
            print(f"Scheduled duty {key} failed: {exc}", file=sys.stderr)
            telegram.send_message(
                chat_id,
                f"({persona['name']} missed the scheduled {key.replace('_', ' ')}: "
                f"{type(exc).__name__}: {exc})",
            )
            continue
        state.append_history(chat_id, persona["name"], reply)
        telegram.send_message(chat_id, f"{persona['emoji']} {persona['name']}:\n{reply}")
        if key == "morning_triage":
            culture_shortlist.mark_triage_announced(state)


def triage_instruction(ctx, now=None):
    """Morning-triage instruction plus the freshly computed work-desk facts
    (inbox sweep, Littler intel, legal tech news; see work_desk.py)."""
    gmail = GmailReader(ctx.get("gmail_token_path"))
    facts = build_work_desk(ctx["vault"], gmail, now)
    culture = culture_shortlist.triage_note(ctx["state"])
    if culture:
        facts += "\n\n" + culture
    print(f"[morning_triage] {facts[:300]!r}", flush=True)
    return SCHEDULED_DUTIES["morning_triage"][1] + "\n\n" + facts


def preview_triage(config, personas_cfg, claude, ctx):
    """Render today's morning triage to stdout without side effects: no
    Telegram send, no history append, no daily-note creation, and the
    persona's write tools are stubbed (ctx dry_run)."""
    allowed = config.get("allowed_chat_ids") or [0]
    ctx = dict(ctx, chat_id=allowed[0], dry_run=True)
    alert = format_alert(cowork_warnings(ctx["vault"], date.today(), []))
    persona = personas_cfg["personas"]["jeeves"]
    instruction = triage_instruction(ctx)
    print("=" * 20, "WORK DESK FACTS", "=" * 20)
    print(instruction.rsplit("WORK DESK FACTS (computed by the bot just now):", 1)[1].strip())
    reply = run_persona_turn(
        claude, config["model"], "jeeves", personas_cfg, instruction, ctx
    )
    print("=" * 20, "PREVIEW (not sent)", "=" * 20)
    if alert:
        print(alert + "\n")
    print(f"{persona['emoji']} {persona['name']}:\n{reply}")


RUN_ALIASES = {
    "sweep": "vault_inbox_sweep",
    "review": "vault_weekly_review",
    "archive": "vault_monthly_archive",
    "notes": "vault_daily_notes",
    "radar": "vault_ai_radar",
}


def run_job_command(text, config, claude, ctx, telegram, chat_id):
    """Handle '/run <sweep|review|archive|notes>': run a Second Brain job now.

    Args:
        text: The full command text.
        config, claude, ctx, telegram, chat_id: As for run_vault_job.
    """
    parts = text.split()
    key = RUN_ALIASES.get(parts[1].lower()) if len(parts) > 1 else None
    if not key:
        telegram.send_message(chat_id, "Usage: /run sweep | review | archive | notes | radar")
        return
    telegram.send_message(chat_id, f"Running {parts[1].lower()} now…")
    run_vault_job(key, config, claude, ctx, telegram, chat_id)
    if key == "vault_daily_notes":
        telegram.send_message(chat_id, "Daily notes checked.")


def run_vault_job(key, config, claude, ctx, telegram, chat_id):
    """Run one Second Brain job; report its result (or failure) in Telegram."""
    started = datetime.now()
    try:
        if key == "vault_daily_notes":
            created = vault_jobs.run_daily_notes(ctx)
            print(f"[{key}] created: {', '.join(created) or 'nothing'}", flush=True)
            return  # silent: nothing for Rebecca to act on
        if key == "vault_ai_radar":
            title = "AI radar"
            summary = ai_radar.run_radar(claude, config["model"], ctx)
        else:
            title = vault_jobs.JOBS[key][0]
            summary = vault_jobs.run_job(key, claude, config["model"], ctx)
    except Exception as exc:
        traceback.print_exc()
        telegram.send_message(
            chat_id, f"⚠️ Second Brain job {key} failed: {type(exc).__name__}: {exc}"
        )
        return
    minutes = (datetime.now() - started).seconds // 60
    print(f"[{key}] done in {minutes} min: {summary[:300]}", flush=True)
    telegram.send_message(chat_id, f"🗂 {title}:\n{summary}")


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
    parser.add_argument(
        "--preview-triage", action="store_true",
        help="print today's morning triage without sending or writing anything",
    )
    args = parser.parse_args()

    config, personas_cfg = load_config()
    alias_map = build_alias_map(personas_cfg)
    telegram = None if args.preview_triage else TelegramClient(load_token(config))
    api_key = load_secret("ANTHROPIC_API_KEY", config, "anthropic_api_key")
    if not api_key:
        raise SystemExit(
            "No Anthropic API key found. Set anthropic_api_key in config.yaml,\n"
            "the ANTHROPIC_API_KEY env var, or .claude/settings.local.json as\n"
            '{"env": {"ANTHROPIC_API_KEY": "sk-ant-..."}}. (Background processes\n'
            "don't read ~/.zshrc, so config.yaml is the reliable option.)"
        )
    claude = anthropic.Anthropic(api_key=api_key)
    state = StateStore(history_limit=config.get("history_limit", 40))
    vault = Vault(config.get("vault_path"))
    # Second Brain jobs (ported from Cowork) are on by default; config.yaml
    # `schedules` can move or disable ("off") them.
    schedules = {**vault_jobs.DEFAULT_SCHEDULES, **(config.get("schedules") or {})}
    scheduler = Scheduler(state, schedules)
    ctx = {
        "state": state,
        "vault": vault,
        "health_export_dir": config.get("health_export_dir"),
        "ring_goals": config.get("ring_goals"),
        "gmail_token_path": config.get("gmail_token_path"),
        "clip_settings": config.get("clips") or {},
    }
    if args.preview_triage:
        preview_triage(config, personas_cfg, claude, ctx)
        return
    start_background_import(
        ctx, config.get("health_import_every_minutes", DEFAULT_EVERY_MINUTES)
    )

    culture_gmail = GmailReader(config.get("gmail_token_path"))
    culture_chat = (config.get("allowed_chat_ids") or [None])[0]
    vault_error = vault.availability_error()
    vault_note = "vault OK" if not vault_error else f"vault UNAVAILABLE: {vault_error}"
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
            if culture_chat is not None:
                try:  # every 30 min, 07:00-22:00; gating lives in the module
                    culture_shortlist.poll(ctx, telegram, culture_chat, culture_gmail)
                except Exception as exc:
                    print(f"[culture] check failed: {type(exc).__name__}: {exc}", flush=True)
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
