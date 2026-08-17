"""Runs one persona turn against the Claude API, including tool-use loops.

History is a shared per-chat transcript (all personas see the same
conversation), injected into the system prompt as a labeled log. This keeps
the Messages API happy regardless of which persona spoke last.
"""

from datetime import datetime

from agent_tools import TOOL_DEFINITIONS, handle_tool_call

MAX_TOOL_ROUNDS = 8
MAX_TOKENS = 2048

WRAP_UP_NOTE = (
    "(System note: the tool budget for this turn is used up. Reply to the "
    "user now in plain text — summarize what you did and relay any tool "
    "errors verbatim so the user knows exactly what failed.)"
)

SHARED_RULES = """
Ground rules for every teammate:
- You are one member of a small team of personas sharing this Telegram chat.
  The team: {roster}.
- Recent chat transcript (speakers labeled) is below; continue it naturally.
- Replies go to Telegram: plain text only, no markdown headers or tables.
  Keep it short — a few sentences unless the user asks for detail.
- Use your tools for reminders, the news digest, the Obsidian vault (notes,
  tasks, reading queue, habit grid), and health data instead of pretending.
- Vault etiquette: you may read any note; writes go only through your
  tools and are append-only. Use append_to_note to file what the user
  dictates: daily-note sections (Worked on, People I talked to, Thinking
  about, Quick capture...), To Try lists (movies, restaurants, books),
  project updates. Never rewrite existing content, and never touch
  auto-generated sections (Sweep flags, Weekly review). New tasks: append
  a '- [ ] ...' line to Tasks/Master.md under the best-fitting section.
  When unsure where something goes, list_vault_files/read_vault_note
  first; ask only if genuinely ambiguous. Today's daily note is
  Daily/<today>.md.
- After filing captures, give a one-line receipt naming each item and its
  destination (e.g. "Filed: plumber → Tasks; Sinners → To Try/Movies") so
  the user can redirect anything you placed wrong. Never create a new
  project note/folder without confirming its name and location first.
- The current local date/time is {now}. Resolve all relative times from it.

Recent transcript (oldest first):
{transcript}
"""


def build_system_prompt(persona_key, personas_cfg, history, now=None):
    """Compose a persona's character prompt plus shared rules and transcript."""
    personas = personas_cfg["personas"]
    persona = personas[persona_key]
    roster = "; ".join(
        f"{p['name']} ({key}) — {p['role'].strip()}" for key, p in personas.items()
    )
    transcript = (
        "\n".join(f"[{entry['speaker']}] {entry['text']}" for entry in history)
        or "(no messages yet)"
    )
    now_str = (now or datetime.now()).strftime("%A %Y-%m-%d %H:%M")
    return persona["system_prompt"].strip() + "\n" + SHARED_RULES.format(
        roster=roster, now=now_str, transcript=transcript
    )


def run_persona_turn(anthropic_client, model, persona_key, personas_cfg, user_text,
                     ctx):
    """Get a persona's reply to user_text, executing any tool calls it makes.

    ctx carries {chat_id, state, vault, health_export_dir}; persona_key is
    added here so tool handlers know who is acting.
    """
    ctx = dict(ctx, persona_key=persona_key)
    system_prompt = build_system_prompt(
        persona_key, personas_cfg, ctx["state"].get_history(ctx["chat_id"])
    )
    messages = [{"role": "user", "content": user_text}]
    for round_no in range(1, MAX_TOOL_ROUNDS + 1):
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = handle_tool_call(block.name, block.input, ctx)
            print(
                f"[tool] {persona_key} round {round_no}: {block.name} -> "
                f"{str(result)[:200]}",
                flush=True,
            )
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )
        messages.append({"role": "user", "content": tool_results})
    else:
        # Budget exhausted while the model still wanted tools. Its last
        # response has no text, so force one final text-only wrap-up
        # instead of sending the user an empty reply.
        print(
            f"[persona_turn] {persona_key}: tool budget exhausted after "
            f"{MAX_TOOL_ROUNDS} rounds, forcing wrap-up",
            flush=True,
        )
        messages[-1]["content"] = list(messages[-1]["content"]) + [
            {"type": "text", "text": WRAP_UP_NOTE}
        ]
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            tool_choice={"type": "none"},
            messages=messages,
        )
    text_parts = [block.text for block in response.content if block.type == "text"]
    reply = "\n".join(text_parts).strip()
    if not reply:
        print(
            f"[persona_turn] {persona_key}: empty reply "
            f"(stop_reason={response.stop_reason})",
            flush=True,
        )
        reply = (
            "(I came back without a reply — the turn ended with "
            f"stop_reason '{response.stop_reason}'. Details are in "
            "~/Library/Logs/agent-team/bot.log.)"
        )
    return reply
