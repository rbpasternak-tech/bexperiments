"""Weekly AI radar: what the vault has been collecting, and what to build.

Reads every clip note, the reading queue (and its archive), the project
notes, ABOUT.md and the week's daily notes, then asks Claude for the
recurring themes, what changed this week, and three ranked project
proposals. Rewrites `Ideas/AI radar.md` (the one note the bot owns
outright) and appends the week's proposals to today's daily note so there
is an append-only history. Proposals are kept in state so a Telegram reply
of "yes 2" creates that project folder from the vault's Project template.
"""

import json
import re
from datetime import date, timedelta

from clip_ingest import parse_json_object

RADAR_NOTE = "Ideas/AI radar.md"
PROPOSALS_KEY = "radar_proposals"
MAX_TOKENS = 16000  # adaptive thinking shares this budget with the JSON
MAX_CLIPS = 80
MAX_QUEUE_LINES = 300
MAX_ARCHIVE_LINES = 350
YES_RE = re.compile(r"^\s*(?:yes|start|go|build|create|project)\s*#?\s*([1-9])\s*[.!]?\s*$", re.I)

RADAR_SYSTEM = """You maintain the "AI radar" note in Rebecca's Obsidian Second Brain.
Rebecca is Director of AI Integration & Enablement at a large law firm, co-author
of a book on AI in legal practice, and builds small personal tools (Python,
vanilla JS, Claude API, Telegram bots, Obsidian automations) in a monorepo
called bexperiments. Read her context and everything she has saved, then
return ONLY a JSON object:
{
 "one_line": "this week's radar in one sentence",
 "themes": [ {"name": "...", "trend": "new|rising|steady|fading",
              "items": <int count of saved items on it>,
              "note": "one sentence: what the saved items collectively say",
              "evidence": ["up to 4 wikilinks [[Note name]] or short titles"]} ],
 "changed_this_week": ["3-6 bullets: new items, shifts, something that resolved"],
 "proposals": [ {"title": "short project name (Title Case, max 6 words)",
                 "outcome": "what done looks like, one sentence",
                 "why_now": "2 sentences tying it to the saved evidence and her role",
                 "evidence": ["3-5 wikilinks [[Note name]] or titles of saved items"],
                 "first_step": "one concrete step doable in an evening",
                 "fit": "bexperiments|Littler|book|personal",
                 "effort": "evening|weekend|ongoing"} ],
 "worth_watching": ["2-4 bullets: threads too early to act on"],
 "top_reads": ["up to 5 titles from the queue most worth her time this week, each with a 5-word reason"]
}
Write for Rebecca in the second person ("you", "your queue"), terse and specific.
Rules: 4-8 themes, ranked by weight. Exactly 3 proposals, ranked; each must be
something she does not already have a project for (see the project list), and
must be grounded in the saved items, not generic advice. Prefer proposals that
reuse what she already runs (the Telegram bot, the vault jobs, the newsletter
digest). Wikilinks must be exact note names given in the input. No prose
outside the JSON."""


def run_radar(claude, model, ctx, today=None):
    """Rebuild the AI radar note and return a Telegram summary.

    Args:
        claude: Anthropic client.
        model: Model id.
        ctx: Bot context with 'vault' and 'state'.
        today: Date override (defaults to today).

    Returns:
        Plain-text summary for Telegram.

    Raises:
        RuntimeError: When the vault is unavailable or the model returns
            nothing usable twice.
    """
    vault, state = ctx["vault"], ctx["state"]
    error = vault.availability_error()
    if error:
        raise RuntimeError(f"vault unavailable: {error}")
    today = today or date.today()
    last = state.get_value("radar_last_run") or {}
    since = last.get("date")
    context, counts = gather_context(vault, today, since)
    data = None
    for _ in range(2):
        response = claude.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=RADAR_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        data = parse_json_object(text)
        if data and data.get("proposals"):
            break
        print(f"[ai_radar] unusable reply (stop_reason={response.stop_reason}, "
              f"{len(text)} chars); retrying", flush=True)
        data = None
    if not data:
        raise RuntimeError(
            f"AI radar: the model returned no usable JSON (last stop_reason="
            f"{response.stop_reason})"
        )
    data = _normalize(data)
    vault.write_note(RADAR_NOTE, render_radar_note(data, today, counts))
    vault.append_section(
        f"Daily/{today.isoformat()}.md", f"AI radar (auto-generated {today.isoformat()})",
        render_daily_section(data),
    )
    state.set_value(PROPOSALS_KEY, {"date": today.isoformat(), "items": data["proposals"]})
    state.set_value("radar_last_run", {"date": today.isoformat()})
    return render_telegram(data, counts)


def gather_context(vault, today, since=None):
    """Assemble the model's input from the vault.

    Args:
        vault: Vault instance.
        today: Run date.
        since: ISO date of the previous run, to flag new items.

    Returns:
        (context_text, counts) where counts summarizes the sources read.
    """
    parts, counts = [], {}
    parts.append("## Rebecca's context (ABOUT.md)\n" + vault.read_note("ABOUT.md", max_chars=5000))
    projects = []
    for rel in vault.list_files("Projects", limit=400):
        if rel.endswith("/index.md") and rel.count("/") == 2:
            name = rel.split("/")[1]
            projects.append(f"### {name}\n" + vault.read_note(rel, max_chars=1200))
    counts["projects"] = len(projects)
    parts.append("## Existing projects (do not re-propose these)\n" + "\n".join(projects))
    ideas = [r for r in vault.list_files("Ideas", limit=200) if not r.endswith("README.md")]
    parts.append("## Ideas notes\n" + "\n".join(ideas))
    clips = _clip_digest(vault, since)
    counts["clips"] = len(clips)
    counts["new_clips"] = sum(1 for c in clips if c["new"])
    parts.append(
        "## Clip notes (Reading/clips/; wikilink by NOTE NAME; new = since last run)\n"
        + "\n".join(_clip_line(c) for c in clips[:MAX_CLIPS])
    )
    queue = _queue_lines(vault.read_note("Reading/queue.md", max_chars=10**6))
    counts["queue"] = len(queue)
    parts.append("## Reading queue items (Reading/queue.md, newest first)\n" + "\n".join(queue[:MAX_QUEUE_LINES]))
    archive = _queue_lines(vault.read_note("Archive/Reading queue archive.md", max_chars=10**6), titles_only=True)
    counts["archive"] = len(archive)
    parts.append("## Older queue items (archived; titles only)\n" + "\n".join(archive[:MAX_ARCHIVE_LINES]))
    parts.append("## Daily notes, past 7 days (Worked on / Thinking about)\n" + _daily_digest(vault, today))
    previous = vault.read_note(RADAR_NOTE, max_chars=12000)
    if not previous.startswith("Note not found"):
        parts.append("## Previous radar note (for trend continuity)\n" + previous)
    parts.append(f"## Today\n{today.isoformat()} ({today:%A}); previous run: {since or 'never'}")
    return "\n\n".join(parts), counts


def _clip_digest(vault, since):
    """Return clip notes as dicts (name, captured, tags, summary, new)."""
    rows = []
    for rel in vault.list_files("Reading/clips", limit=2000):
        if rel.endswith("README.md"):
            continue
        meta = vault.note_frontmatter(rel)
        text = vault.read_note(rel, max_chars=6000)
        summary = re.search(r"## Summary\n(.*?)(?:\n## |\Z)", text, re.S)
        rows.append({
            "name": rel.rsplit("/", 1)[-1][:-3],
            "captured": meta.get("captured", ""),
            "tags": meta.get("tags", "").strip("[]"),
            "source": meta.get("source", ""),
            "summary": (summary.group(1).strip() if summary else "")[:500],
            "new": bool(since) and meta.get("captured", "") > since,
        })
    rows.sort(key=lambda r: r["captured"], reverse=True)
    return rows


def _clip_line(clip):
    """One-line rendering of a clip for the model input."""
    flag = " [NEW]" if clip["new"] else ""
    return (f"- [[{clip['name']}]]{flag} ({clip['captured']}, {clip['source']}; "
            f"tags: {clip['tags']}) — {clip['summary']}")


def _queue_lines(text, titles_only=False):
    """Return the queue's item lines, optionally reduced to bold titles."""
    lines = []
    for line in text.splitlines():
        if not line.startswith("- ["):
            continue
        if titles_only:
            title = re.search(r"\*\*(.+?)\*\*", line)
            lines.append("- " + (title.group(1) if title else line[6:80]))
        else:
            lines.append(line[:600])
    return lines


def _daily_digest(vault, today):
    """Pull 'Worked on' and 'Thinking about' bullets from the past week."""
    out = []
    for back in range(7):
        day = (today - timedelta(days=back)).isoformat()
        text = vault.read_note(f"Daily/{day}.md", max_chars=20000)
        if text.startswith("Note not found"):
            continue
        for heading in ("Worked on", "Thinking about", "Quick capture"):
            found = re.search(rf"## {heading}\n(.*?)(?:\n## |\Z)", text, re.S)
            bullets = [l for l in (found.group(1).splitlines() if found else []) if l.strip() not in ("", "-")]
            if bullets:
                out.append(f"{day} {heading}: " + " | ".join(b.strip() for b in bullets)[:600])
    return "\n".join(out) or "(no daily-note content this week)"


def _normalize(data):
    """Fill defaults and clamp lists so rendering never breaks."""
    data = dict(data)
    data["one_line"] = str(data.get("one_line") or "").strip()
    data["themes"] = [t for t in (data.get("themes") or []) if isinstance(t, dict) and t.get("name")][:8]
    for theme in data["themes"]:
        theme.setdefault("trend", "steady")
        theme.setdefault("items", "")
        theme.setdefault("note", "")
        theme["evidence"] = [str(e) for e in (theme.get("evidence") or [])][:4]
    proposals = []
    for p in (data.get("proposals") or [])[:3]:
        if isinstance(p, dict) and p.get("title"):
            for key in ("outcome", "why_now", "first_step", "fit", "effort"):
                p[key] = str(p.get(key) or "").strip()
            p["title"] = str(p["title"]).strip()[:60]
            p["evidence"] = [str(e) for e in (p.get("evidence") or [])][:5]
            proposals.append(p)
    data["proposals"] = proposals
    for key in ("changed_this_week", "worth_watching", "top_reads"):
        data[key] = [str(x).strip() for x in (data.get(key) or []) if str(x).strip()][:6]
    return data


def render_radar_note(data, today, counts):
    """Render Ideas/AI radar.md."""
    lines = [
        "# AI radar", "",
        f"_Rebuilt weekly by the Household Staff bot; last run {today.isoformat()}. "
        "This note is rewritten each time — the weekly history is in the daily notes "
        "under \"AI radar\". Sources this run: "
        f"{counts.get('clips', 0)} clip notes ({counts.get('new_clips', 0)} new), "
        f"{counts.get('queue', 0)} queue items, {counts.get('archive', 0)} archived, "
        f"{counts.get('projects', 0)} projects._", "",
        f"**This week in one line:** {data['one_line']}", "",
        "## Themes", "", "| Theme | Trend | Items | What the saved items say |", "|---|---|---|---|",
    ]
    for t in data["themes"]:
        lines.append(f"| {t['name']} | {t['trend']} | {t['items']} | {t['note']} |")
    lines.append("")
    for t in data["themes"]:
        if t["evidence"]:
            lines.append(f"- **{t['name']}:** " + "; ".join(t["evidence"]))
    lines += ["", "## What changed this week"] + [f"- {c}" for c in data["changed_this_week"]]
    lines += ["", "## Project proposals", "",
              "_Reply `yes N` in Telegram to create `Projects/<title>/` from the template._", ""]
    for i, p in enumerate(data["proposals"], 1):
        lines += [
            f"### {i}. {p['title']}",
            f"**Outcome:** {p['outcome']}",
            f"**Why now:** {p['why_now']}",
            "**Evidence:** " + "; ".join(p["evidence"]),
            f"**First step:** {p['first_step']}",
            f"**Fit / effort:** {p['fit']} / {p['effort']}", "",
        ]
    if data["top_reads"]:
        lines += ["## Read this week"] + [f"- {r}" for r in data["top_reads"]] + [""]
    if data["worth_watching"]:
        lines += ["## Worth watching"] + [f"- {w}" for w in data["worth_watching"]] + [""]
    return "\n".join(lines)


def render_daily_section(data):
    """Body of the daily-note section (append-only weekly history)."""
    lines = [data["one_line"], "", "**Proposals** (reply `yes N` in Telegram to start one):"]
    for i, p in enumerate(data["proposals"], 1):
        lines.append(f"{i}. **{p['title']}** — {p['why_now']} First step: {p['first_step']}")
    if data["top_reads"]:
        lines += ["", "**Read this week:**"] + [f"- {r}" for r in data["top_reads"]]
    lines += ["", "Full note: [[AI radar]]"]
    return "\n".join(lines)


def render_telegram(data, counts):
    """Short plain-text report for Telegram."""
    lines = [data["one_line"], ""]
    lines.append("Themes: " + ", ".join(f"{t['name']} ({t['trend']})" for t in data["themes"][:6]))
    lines.append("")
    lines.append("Projects you could start (reply 'yes N'):")
    for i, p in enumerate(data["proposals"], 1):
        lines.append(f"{i}. {p['title']} — {p['outcome']} [{p['effort']}]")
    lines.append("")
    lines.append(f"Read {counts.get('clips', 0)} clips ({counts.get('new_clips', 0)} new) "
                 f"and {counts.get('queue', 0)} queue items. Full note: Ideas/AI radar.md")
    return "\n".join(lines)


def match_yes(text, state):
    """Return the proposal chosen by a 'yes N' reply, or None.

    Args:
        text: Incoming message text.
        state: StateStore holding the latest proposals.

    Returns:
        (index, proposal) when the text is 'yes N' and proposal N exists.
    """
    found = YES_RE.match(text or "")
    if not found:
        return None
    stored = state.get_value(PROPOSALS_KEY) or {}
    items = stored.get("items") or []
    index = int(found.group(1))
    if index > len(items):
        return None
    return index, items[index - 1]


def create_project_from_proposal(vault, proposal, today=None):
    """Create Projects/<title>/index.md from the vault template.

    Args:
        vault: Vault instance.
        proposal: One proposal dict from the radar.
        today: Date override.

    Returns:
        The vault-relative index path, or an error message from the vault.
    """
    today = (today or date.today()).isoformat()
    template = vault.read_template("Templates/Project index.md")
    title = proposal["title"]
    if template:
        body = template.replace("{{project name}}", title)
        body = re.sub(r"\{\{date(?::[^}]*)?\}\}", today, body)
        body = body.replace("**Status:** active / blocked / dormant", "**Status:** active")
        body = body.replace('**Outcome:** _what does "done" look like?_', f"**Outcome:** {proposal['outcome']}")
        body = body.replace("**Target:** ", f"**Target:** first step — {proposal['first_step']}")
        body = body.replace("_one paragraph — what's the motivation, what's the stake_", proposal["why_now"])
        body = body.replace(
            "_where are we right now, what just happened, what's next_",
            f"Created from the AI radar on {today}. Next: {proposal['first_step']}",
        )
        body = body.replace("## Key links\n- ", "## Key links\n- [[AI radar]]\n" + "".join(f"- {e}\n" for e in proposal["evidence"]).rstrip("\n"))
        body = body.replace("## Open threads\n- [ ] ", f"## Open threads\n- [ ] {proposal['first_step']}")
        body = body.replace(f"- {today} — ", f"- {today} — Started from AI radar proposal ({proposal.get('fit', '')}, {proposal.get('effort', '')})")
    else:
        body = (f"# {title}\n\n**Status:** active\n**Outcome:** {proposal['outcome']}\n"
                f"**Started:** {today}\n\n## Why this matters\n{proposal['why_now']}\n\n"
                f"## Open threads\n- [ ] {proposal['first_step']}\n")
    return vault.create_project(title, body)
