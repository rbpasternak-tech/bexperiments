# Agent Team — Next Steps

Pickup plan. Tell Claude "work through agent-team/NEXT-STEPS.md" to resume.
Interview done 2026-07-26 — decisions below are settled; build order at the end.

## Where things stand

Built and pushed on `claude/plan-mode-w2mq4s`:

- One Telegram bot, four classic-literature personas (Jeeves 🎩 chief of
  staff, Elizabeth Bennet 📖 accountability, Gatsby 🥂 celebration,
  Bartleby 🖋️ deadpan nudges) — voices in `personas.yaml`
- Haiku router or direct address ("Jeeves, ..."); shared per-chat memory;
  timed reminders via tool use; reads the trends-dashboard digest
- Offline-tested; not yet run live (bot token lives only on your Mac —
  `telegram_bot.py` was always gitignored, never committed, nothing lost)

## Interview results — duties per persona

| Persona | Duty |
|---|---|
| Jeeves | **7:00 am morning triage**: reads new self-sent emails, presents numbered task list + today's reminders in Telegram; tracks "done 2" / "snooze 3" state. General planning + routing. |
| Elizabeth Bennet | Task accountability: calls out perpetually-snoozed items, cuts scope. Owns **reading capture** — forward a link/title/thought and she files it in the vault. |
| Gatsby | Weekly wins recap from tracker data; rewards and breaks. |
| Bartleby | **Nightly habit check-in** (one-line answer: rings, book/audiobook, vibration plate, red light) and writes the weekly tracker note in the vault. |

Explicitly NOT in scope: the two briefs (Littler competitor intel codex
agent + legal tech project) — they work, leave them alone.

## Guardrails (user-set)

- Allowed without asking: **read Gmail**, **write to the Obsidian vault**
- Ask first: archiving/labeling emails
- Never: send email as the user

## Data flows decided

1. **Health tracker** (was: typed manually — biggest win)
   - Install **Health Auto Export** (iPhone) → scheduled JSON/CSV to an
     iCloud folder. Covers steps/activity, weight, sleep, rings, AND
     MyFitnessPal nutrition (MFP → Apple Health sync; MFP has no public API).
   - Manual habits (physical book vs audiobook, vibration plate, red light)
     via Bartleby's nightly Telegram check-in.
   - Bot merges both → writes the weekly tracker note in the vault.
2. **Tasks**: keep email-to-self as capture. Jeeves triages at 7am;
   task state lives in bot state; Gmail read-only.
3. **Reading capture** (pain: capture friction): forward anything to the
   bot → Bennet appends to the vault's read/unread/need-to-read notes.
   Retrieval/Q&A over the vault is a later phase.

## Connectors checklist

| Need | How | Status |
|---|---|---|
| Telegram | existing bot token on Mac | ready, just wire config |
| Claude API | ANTHROPIC_API_KEY | ready |
| Gmail read-only | reuse `newsletter-digest/gmail_client.py` OAuth pattern + existing `credentials.json`; new token with readonly scope at `agent-team/token.json` (gitignore it) | build tomorrow |
| Apple Health / MFP | Health Auto Export app → iCloud folder; bot reads files (no API exists) | install app tomorrow |
| Obsidian vault | plain filesystem on Mac — locate the vault folder first (user unsure where it lives) | locate tomorrow |
| 7am brief + nightly check-in | recurring entries in the bot's polling loop (like reminders — no new infra) | build tomorrow |

## Tomorrow, in order

1. **On your Mac (15 min, needs you):**
   a. Run the bot once (README Setup) so Jeeves answers in Telegram.
   b. Find the vault: in Obsidian, right-click a note → "Reveal in Finder";
      tell Claude the path. Note the tracker note's format (or share it).
   c. Install Health Auto Export; schedule a daily export (JSON) to an
      iCloud Drive folder; tell Claude that path too.
2. **Then Claude builds (roughly in this order):**
   a. `vault.py` — locate/read/write vault notes; reading-capture tool
      for Bennet; tracker-note writer.
   b. `gmail_reader.py` — readonly OAuth (reuse gmail_client pattern),
      "self-sent since yesterday" query; task state in StateStore.
   c. Recurring schedules: 7am Jeeves triage, ~9pm Bartleby check-in
      (extend the reminder loop with repeating entries).
   d. `health_import.py` — parse Health Auto Export output, merge with
      check-in answers, render the weekly tracker note.
   e. Update persona prompts with their new duties + tools; test each
      flow live in Telegram; commit (never commit token.json/credentials).
3. **Later / day after:** vault Q&A ("what did I say about X?"),
   need-to-read triage, always-on via launchd, weekly Gatsby wins recap.
