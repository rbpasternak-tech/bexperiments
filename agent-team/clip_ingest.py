"""Turn a shared link or video into a clip note in the vault.

Pipeline: fetch (clips.py) → summarize with Claude against Rebecca's current
context (ABOUT.md, project names) → write Reading/clips/<date> <title>.md
with frontmatter, summary, key claims and the full transcript/text → add a
one-line pointer to today's daily note. When a fetch fails (Instagram
without login, a paywall), the caller asks Rebecca for the caption and
files that instead, so nothing shared is lost.
"""

import json
import re
import threading
from datetime import date, datetime

from clips import ClipError, fetch_clip, site_of, transcribe_file

MAX_TEXT_CHARS = 30000
SUMMARY_MAX_TOKENS = 4000  # adaptive thinking shares this budget with the JSON
DAILY_SECTION = "Articles / links to read"

# One ingest at a time: Whisper needs the RAM, and the summaries read the
# vault's clip list for dedupe.
_INGEST_LOCK = threading.Lock()

SUMMARY_SYSTEM = """You file saved links into Rebecca's Obsidian Second Brain.
Given a video transcript (or caption) or article text plus metadata, return
ONLY a JSON object with these keys:
- "title": a clean, specific title (max 80 chars; not clickbait, no emoji).
- "summary": 2-4 sentences saying what it actually claims or shows — specifics,
  numbers, names, the mechanism — not a restatement of the title.
- "key_claims": 2-6 short bullet strings, each one concrete claim, step, tool,
  or number from the content.
- "tags": 2-5 kebab-case topic tags (e.g. "ai-agents", "legal-tech",
  "claude-code", "prompting", "obsidian", "productivity", "ai-policy").
  Reuse the existing tags listed when they fit.
- "why_it_matters": one sentence on how this connects to Rebecca's active
  threads (below), or "" if it plainly does not.
- "related_projects": names from the project list below that this genuinely
  relates to (often empty).
- "actionable": one concrete thing Rebecca could try from this, or "".
Write for Rebecca in the second person ("your Littler deck", not "Rebecca's").
No prose outside the JSON."""


def looks_like_capture(text):
    """True when a message is a share: a URL with at most a short note.

    Args:
        text: The incoming Telegram message text.

    Returns:
        True when the message contains a URL and the non-URL remainder is
        short (a note, not a conversation).
    """
    from clips import find_urls

    urls = find_urls(text)
    if not urls:
        return False
    remainder = text
    for url in urls:
        remainder = remainder.replace(url, " ")
    return len(remainder.strip()) <= 400


def ingest_capture(ctx, claude, model, url=None, note="", video_path=None,
                   caption=None, source="telegram"):
    """File one shared item as a clip note.

    Args:
        ctx: Bot context with 'vault', 'state', and 'clip_settings'.
        claude: Anthropic client.
        model: Model id for the summary call.
        url: The shared link (None when a video file was sent).
        note: Rebecca's own words sent with the link ("why I saved it").
        video_path: Local media file to transcribe instead of fetching url.
        caption: Text Rebecca pasted after a failed fetch; used as content.
        source: Where the capture came from (frontmatter `via`).

    Returns:
        A dict: ok (bool), path (vault-relative note path when ok), title,
        summary, tags, related, error (message when not ok), and
        needs_caption (True when asking Rebecca for the text would help).
    """
    vault = ctx["vault"]
    settings = ctx.get("clip_settings") or {}
    with _INGEST_LOCK:
        if url:
            existing = vault.clip_urls().get(_clean(url))
            if existing:
                return {"ok": True, "path": existing, "title": existing, "summary": "",
                        "tags": [], "related": [], "already": True}
        try:
            content = _gather_content(url, video_path, caption, settings)
        except ClipError as exc:
            return {"ok": False, "error": str(exc), "needs_caption": True}
        content["note"] = (note or "").strip()
        content["via"] = source
        summary = _summarize(claude, model, vault, content)
        stem = f"{date.today().isoformat()} {summary['title']}"
        body = render_clip_note(content, summary, date.today())
        path = vault.write_clip_note(stem, body)
        if not path.endswith(".md"):
            return {"ok": False, "error": path, "needs_caption": False}
        _link_from_daily_note(vault, path, summary, content)
        return {
            "ok": True, "path": path, "title": summary["title"],
            "summary": summary["summary"], "tags": summary["tags"],
            "related": summary["related_projects"], "already": False,
            "actionable": summary.get("actionable", ""),
        }


def _gather_content(url, video_path, caption, settings):
    """Produce the content dict from whichever input we have."""
    if caption is not None:
        return {
            "kind": "caption", "url": url or "", "site": site_of(url) if url else "note",
            "title": "", "creator": "", "description": "", "duration": None,
            "published": "", "text": caption.strip(), "text_kind": "caption",
            "language": None, "truncated": False,
        }
    if video_path:
        text, language, truncated = transcribe_file(video_path, settings)
        if not text:
            raise ClipError("the video had no speech to transcribe")
        return {
            "kind": "video", "url": url or "", "site": "telegram-video", "title": "",
            "creator": "", "description": "", "duration": None, "published": "",
            "text": text, "text_kind": "transcript", "language": language,
            "truncated": truncated,
        }
    content = fetch_clip(url, settings)
    if not content["text"] and not content["description"]:
        raise ClipError("nothing to transcribe or read at that link")
    return content


def _summarize(claude, model, vault, content):
    """Ask Claude for the note's title, summary, claims and tags (JSON)."""
    about = vault.read_note("ABOUT.md", max_chars=4000)
    projects = sorted({
        rel.split("/")[1] for rel in vault.list_files("Projects", limit=500)
        if rel.count("/") >= 2
    })
    tags = _existing_tags(vault)
    payload = {
        "kind": content["kind"], "site": content["site"], "url": content["url"],
        "original_title": content["title"], "creator": content["creator"],
        "published": content["published"], "duration_seconds": content["duration"],
        "rebecca_note": content["note"], "caption_or_description": content["description"][:3000],
        content["text_kind"]: content["text"][:MAX_TEXT_CHARS],
    }
    user = (
        f"Rebecca's context (ABOUT.md):\n{about}\n\n"
        f"Project list: {', '.join(projects) or '(none)'}\n"
        f"Existing clip tags: {', '.join(tags) or '(none yet)'}\n\n"
        f"Item to file:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    fallback = {
        "title": content["title"] or f"Clip from {content['site']}",
        "summary": content["text"][:400], "key_claims": [], "tags": [],
        "why_it_matters": "", "related_projects": [], "actionable": "",
    }
    for attempt in range(2):
        response = claude.messages.create(
            model=model, max_tokens=SUMMARY_MAX_TOKENS, system=SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        parsed = parse_json_object(text)
        if parsed and parsed.get("title"):
            break
        parsed = None
    result = dict(fallback, **(parsed or {}))
    result["title"] = str(result["title"]).strip()[:80] or fallback["title"]
    result["tags"] = [_tagify(t) for t in (result.get("tags") or []) if _tagify(t)][:5]
    result["key_claims"] = [str(c).strip() for c in (result.get("key_claims") or []) if str(c).strip()]
    result["related_projects"] = [p for p in (result.get("related_projects") or []) if p in projects]
    return result


def render_clip_note(content, summary, today):
    """Render the clip note markdown (frontmatter + sections).

    Args:
        content: Dict from _gather_content.
        summary: Dict from _summarize.
        today: The capture date.

    Returns:
        The full note text.
    """
    duration = _fmt_duration(content["duration"])
    front = [
        "---", "type: clip", f"source: {content['site']}", f"url: {content['url']}",
        f"captured: {today.isoformat()}", f"title: {_yaml_str(summary['title'])}",
        f"creator: {_yaml_str(content['creator'])}", f"published: {content['published']}",
        f"duration: {duration}", f"via: {content['via']}",
        f"tags: [{', '.join(summary['tags'])}]", "---",
    ]
    body = [f"# {summary['title']}", ""]
    body.append(f"**Why I saved it:** {content['note'] or '_(no note)_'}")
    origin = f"{content['creator']} on {content['site']}" if content["creator"] else content["site"]
    body.append(f"**Source:** {origin}" + (f" — {content['url']}" if content["url"] else ""))
    if summary["related_projects"]:
        body.append("**Related:** " + ", ".join(f"[[{p}]]" for p in summary["related_projects"]))
    if summary.get("why_it_matters"):
        body.append(f"**Why it matters:** {summary['why_it_matters']}")
    if summary.get("actionable"):
        body.append(f"**Try:** {summary['actionable']}")
    body += ["", "## Summary", summary["summary"].strip(), ""]
    if summary["key_claims"]:
        body += ["## Key claims"] + [f"- {c}" for c in summary["key_claims"]] + [""]
    if content["description"] and content["kind"] == "video":
        body += ["## Caption", content["description"].strip(), ""]
    heading = {"transcript": "Transcript", "article": "Article text", "caption": "Caption / pasted text"}
    label = heading.get(content["text_kind"], "Text")
    if content["truncated"]:
        label += " (first part only)"
    if content.get("language") and content["language"] != "en":
        label += f" ({content['language']})"
    body += [f"## {label}", content["text"].strip() or "_(none)_"]
    return "\n".join(front + [""] + body)


def _link_from_daily_note(vault, path, summary, content):
    """Append a one-line pointer to today's daily note (append-only)."""
    stem = path.rsplit("/", 1)[-1][:-3]
    first = re.split(r"(?<=[.!?])\s", summary["summary"].strip(), maxsplit=1)[0]
    line = f"- 📎 [[{stem}]] ({content['site']}) — {first}"
    vault.append_under_section(f"Daily/{date.today().isoformat()}.md", DAILY_SECTION, line)


def _existing_tags(vault):
    """Collect tags already used across clip notes (for consistency)."""
    tags = set()
    for rel in vault.list_files("Reading/clips", limit=2000):
        raw = vault.note_frontmatter(rel).get("tags", "")
        for tag in raw.strip("[]").split(","):
            if tag.strip():
                tags.add(tag.strip())
    return sorted(tags)[:60]


def parse_json_object(text):
    """Extract the first JSON object from model output, or None."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _tagify(tag):
    """Normalize a tag to kebab-case without a leading '#'."""
    tag = re.sub(r"[^a-z0-9]+", "-", str(tag).lower().lstrip("#")).strip("-")
    return tag[:40]


def _yaml_str(value):
    """Quote a scalar for frontmatter."""
    return json.dumps(str(value or ""), ensure_ascii=False)


def _fmt_duration(seconds):
    """Format seconds as m:ss (or '' when unknown)."""
    if not seconds:
        return ""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _clean(url):
    """Trim trailing punctuation for dedupe (same rule as vault.py)."""
    return url.rstrip(".,;:!?*_")


def format_receipt(result, url=None):
    """Render the Telegram reply for an ingest result.

    Args:
        result: Dict from ingest_capture.
        url: The original link, for the failure message.

    Returns:
        Plain text for Telegram.
    """
    if not result["ok"]:
        text = f"📎 Couldn't fetch {url or 'that'}: {result['error']}."
        if result.get("needs_caption"):
            text += ("\nPaste the caption or what it said and I'll file that instead "
                     "(or reply 'skip').")
        return text
    if result.get("already"):
        return f"📎 Already filed: {result['path']}"
    lines = [f"📎 Filed: {result['path']}", "", result["summary"]]
    if result.get("actionable"):
        lines += ["", f"Try: {result['actionable']}"]
    if result["tags"]:
        lines.append("Tags: " + ", ".join(result["tags"]))
    if result["related"]:
        lines.append("Related: " + ", ".join(result["related"]))
    return "\n".join(lines)


def run_capture_async(ctx, claude, model, telegram, chat_id, **kwargs):
    """Run ingest_capture on a thread and post the receipt to Telegram.

    Args:
        ctx, claude, model: As for ingest_capture.
        telegram: TelegramClient for the receipt.
        chat_id: Chat to reply in.
        **kwargs: Passed to ingest_capture (url, note, video_path, caption).
    """
    def work():
        try:
            result = ingest_capture(ctx, claude, model, **kwargs)
        except Exception as exc:  # never let a capture kill the thread silently
            import traceback
            traceback.print_exc()
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "needs_caption": False}
        url = kwargs.get("url")
        if not result["ok"] and result.get("needs_caption") and url:
            ctx["state"].set_value(f"pending_clip:{chat_id}", {
                "url": url, "note": kwargs.get("note", ""),
                "asked_at": datetime.now().isoformat(),
            })
        receipt = format_receipt(result, url)
        print(f"[clip] {receipt[:200]}", flush=True)
        telegram.send_message(chat_id, receipt)
        ctx["state"].append_history(chat_id, "Clips", receipt)

    threading.Thread(target=work, name="clip-ingest", daemon=True).start()
