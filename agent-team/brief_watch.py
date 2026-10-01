"""Tech-experiment and project activity for the morning brief (read-only).

Two lines of the 7:00 triage come from here, each only when something is new
since the previous triage:

- Tech experiments: notes in To-try/Tech experiments/ that are new, or whose
  frontmatter `status` changed (last-seen statuses kept in WATCH_FILE).
- Projects: notes under Projects/ modified since the last triage, with one
  line on what changed (new open tasks, new headings, first new line).
  Files whose current content is exactly what the bot itself last wrote
  (BOT_WRITES_FILE, recorded by Vault.record_bot_write) are skipped as
  bot-only. Edits made by other tools (e.g. Grok) can't be told apart.

collect() never writes; commit() saves the new baseline and is called only
after the live triage was delivered (never from --preview-triage).
"""

import hashlib
import json
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

STATE_DIR = Path.home() / "Library" / "Application Support" / "agent-team"
WATCH_FILE = STATE_DIR / "triage-watch.json"
BOT_WRITES_FILE = STATE_DIR / "bot-writes.json"
TECH_DIR = "To-try/Tech experiments"
PROJECTS_DIR = "Projects"
MAX_LINES_KEPT = 4000


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def _sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _line_keys(text):
    """Short hashes of each non-blank line (for 'what's new' diffs)."""
    return sorted({_sha(l.strip())[:12] for l in text.splitlines() if l.strip()})[:MAX_LINES_KEPT]


def _md_files(root, sub):
    base = root / sub
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.md") if not any(part.startswith(".") for part in p.parts))


def collect(vault, now=None):
    """Return (facts_text, new_watch_state). Pure read."""
    now = now or datetime.now()
    watch = _read_json(WATCH_FILE, {})
    first_run = not watch
    since = datetime.fromisoformat(watch["last_triage"]) if watch.get("last_triage") else \
        datetime.combine(now.date() - timedelta(days=1), dtime(7, 0))
    new_state = {"last_triage": now.isoformat(timespec="seconds"), "tech": {}, "projects": {}}
    if not vault.available():
        return "Tech experiments / Projects: vault unavailable.", None
    root = vault.root

    # --- tech experiments ---
    tech_lines = []
    old_tech = watch.get("tech", {})
    for path in _md_files(root, TECH_DIR):
        rel = str(path.relative_to(root))
        if path.name == "index.md":
            continue
        meta = vault.note_frontmatter(rel)
        status = meta.get("status", "").strip('"\' ') or "(none)"
        title = meta.get("title", "").strip('"\' ') or path.stem
        new_state["tech"][rel] = {"status": status}
        prev = old_tech.get(rel)
        if prev is None:
            added = datetime.fromtimestamp(path.stat().st_birthtime if hasattr(path.stat(), "st_birthtime") else path.stat().st_mtime)
            if not first_run or added >= since:
                tech_lines.append(f"- NEW: {title} (status {status})")
        elif prev.get("status") != status:
            tech_lines.append(f"- {title}: status {prev.get('status')} → {status}")

    # --- projects ---
    bot_writes = _read_json(BOT_WRITES_FILE, {})
    old_proj = watch.get("projects", {})
    proj_lines = []
    for path in _md_files(root, PROJECTS_DIR):
        rel = str(path.relative_to(root))
        try:
            text = path.read_text()
        except OSError:
            continue
        sha = _sha(text)
        keys = _line_keys(text)
        new_state["projects"][rel] = {"sha": sha, "lines": keys}
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        prev = old_proj.get(rel)
        if prev and prev.get("sha") == sha:
            continue
        if not prev and mtime < since:
            continue
        if bot_writes.get(rel) == sha:
            continue  # last writer was the bot itself; nothing she did
        parts = rel.split("/")
        project = parts[1] if len(parts) > 2 else path.stem
        note = "/".join(parts[2:]) if len(parts) > 2 else path.name
        if prev:
            old_keys = set(prev.get("lines", []))
            added = [l.strip() for l in text.splitlines()
                     if l.strip() and _sha(l.strip())[:12] not in old_keys]
            tasks = [l for l in added if l.startswith(("- [ ]", "* [ ]"))]
            heads = [l.lstrip("#").strip() for l in added if l.startswith("#")]
            bits = []
            if tasks:
                bits.append(f"{len(tasks)} new open task(s), e.g. \"{tasks[0][6:80]}\"")
            if heads:
                bits.append("new section(s): " + ", ".join(h[:50] for h in heads[:2]))
            if not bits and added:
                bits.append(f"new line: \"{added[0][:90]}\"")
            if not bits:
                bits.append("lines removed or reworded")
            proj_lines.append(f"- {project} ({note}): " + "; ".join(bits))
        else:
            proj_lines.append(f"- {project} ({note}): {'new note' if first_run is False else 'edited'} "
                              f"{mtime:%a %-I:%M %p} (no earlier snapshot to diff)")

    tech = ("Tech experiments: NEW since last triage —\n" + "\n".join(tech_lines)) if tech_lines \
        else "Tech experiments: NOTHING NEW (omit the line)."
    proj = ("Projects: ACTIVITY since last triage —\n" + "\n".join(proj_lines[:6])) if proj_lines \
        else "Projects: NOTHING NEW (omit the line)."
    return f"{tech}\n\n{proj}", new_state


def commit(new_state):
    """Save the baseline after a delivered live triage."""
    if not new_state:
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = WATCH_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(new_state, indent=1))
    tmp.replace(WATCH_FILE)
