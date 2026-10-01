"""Read/write helpers for the Obsidian vault (plain markdown files on disk).

The vault is iCloud-synced but locally it's just a folder, so the bot reads
and writes files directly. Writes are append-only: the habit grid
(Tracking/Habits/), the reading queue Inbox, task checkboxes in
Tasks/Master.md, and single lines appended under a section heading
(append_under_section, e.g. daily-note captures), approved NYC Culture
Shortlist picks appended to the end of To-try/Culture.md
(append_culture_lines — the only write target for that flow), plus new notes
(clip notes, project folders). Two exceptions, both deliberate: the
weekly cleanup moves stale queue subsections to the archive and promotes
queue items into theme sections, and the AI radar rewrites its own note.
"""

import calendar
import errno
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

READING_QUEUE = "Reading/queue.md"
DAILY_DIR = "Daily"
DAILY_TEMPLATE = "Templates/Daily.md"
_DAILY_NOTE_RE = re.compile(r"^Daily/(\d{4}-\d{2}-\d{2})\.md$")
_TEMPLATE_DATE_RE = re.compile(r"\{\{date(?::[^}]*)?\}\}")
TASKS_MASTER = "Tasks/Master.md"
CULTURE_LIST = "To-try/Culture.md"
HABITS_DIR = "Tracking/Habits"
CLIPS_DIR = "Reading/clips"
QUEUE_ARCHIVE = "Archive/Reading queue archive.md"
PROJECTS_DIR = "Projects"
PROJECT_TEMPLATE = "Templates/Project index.md"
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_FILENAME_BAD_RE = re.compile(r'[\\/:*?"<>|#^\[\]]+')

CLIPS_README = """# Clips

One note per link or video shared to the Household Staff bot (Telegram):
frontmatter (source, url, tags), a summary, key claims, and the full
transcript or article text so the vault holds what the thing actually said —
not just a URL. `Ideas/AI radar.md` is rebuilt from these every week.

Filenames: `YYYY-MM-DD <title>.md`. Written by the bot; edit freely — the bot
never rewrites a clip note.
"""

# The background health import and persona tool calls can both write the
# habit grid; serialize the read-modify-write so neither loses the other's cells.
_HABIT_WRITE_LOCK = threading.Lock()


class Vault:
    """Filesystem access to the vault, guarded against path escapes."""

    def __init__(self, vault_path):
        """Remember the vault root; a falsy path means 'not configured'."""
        self.root = Path(vault_path).expanduser() if vault_path else None

    def available(self):
        """Return True when the vault folder exists on this machine."""
        return self.availability_error() is None

    def availability_error(self):
        """Return None when the vault is usable, else the specific reason.

        Distinguishes 'not configured', 'folder missing', and 'macOS denied
        access' — the last one is what a launchd-run bot sees for iCloud
        folders (~/Library/Mobile Documents) without Full Disk Access.
        """
        if not self.root:
            return "no vault_path configured in config.yaml"
        try:
            os.stat(self.root)
        except PermissionError:
            return (
                f"macOS denied access to {self.root} — if the bot runs "
                "under launchd, grant Full Disk Access to its Python binary "
                "(System Settings > Privacy & Security), or run it from "
                "Terminal"
            )
        except OSError:
            return f"vault folder does not exist: {self.root}"
        if not self.root.is_dir():
            return f"vault path is not a folder: {self.root}"
        return None

    def _unavailable_message(self):
        """Return the user-facing string for a failed availability check."""
        return f"Vault not available: {self.availability_error()}."

    def _resolve(self, relative):
        """Resolve a vault-relative path, refusing anything outside the root."""
        path = (self.root / relative).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"Path escapes vault: {relative}")
        return path

    def habit_row_cells(self, date_str):
        """Return {column: cell_text} for a date's habit row, or None.

        None means the month grid or the date's row does not exist. Used by
        the deterministic nightly recorder to tell which cells are already
        filled so it never clobbers a value the user corrected by hand.
        """
        if not self.available():
            return None
        path = self._resolve(f"{HABITS_DIR}/{date_str[:7]}.md")
        if not path.is_file():
            return None
        lines = _read_text(path).splitlines()
        columns = _find_table_columns(lines)
        if not columns:
            return None
        for line in lines:
            cells = _split_row(line)
            if cells and cells[0] == date_str:
                return {
                    col: (cells[i] if i < len(cells) else "")
                    for i, col in enumerate(columns)
                }
        return None

    def read_note(self, relative, max_chars=8000):
        """Return a note's text (truncated), or an explanatory message."""
        if not self.available():
            return self._unavailable_message()
        path = self._resolve(relative)
        if not path.is_file():
            return f"Note not found: {relative}"
        text = _read_text(path)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[... truncated ...]"
        return text

    def list_files(self, subpath="", limit=200):
        """List vault-relative .md paths under subpath (skips dot-folders)."""
        if not self.available():
            return []
        base = self._resolve(subpath) if subpath else self.root
        if not base.is_dir():
            return []
        found = []
        for path in sorted(base.rglob("*.md")):
            rel = path.relative_to(self.root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            found.append(str(rel))
            if len(found) >= limit:
                break
        return found

    def append_under_section(self, relative, section, line):
        """Append one line under a heading in a note. Append-only: never
        rewrites existing content. Creates the section (and the note) if
        missing. Returns a status message."""
        if not self.available():
            return self._unavailable_message()
        if not relative.endswith(".md"):
            return "Can only append to .md notes."
        path = self._resolve(relative)
        daily = _DAILY_NOTE_RE.match(relative)
        if not path.is_file() and daily:
            # A daily note gets the full template, not a one-section stub:
            # a stub would also block the template from ever being applied.
            self.create_daily_note(daily.group(1))
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"## {section}\n{line}\n")
            return f"Created {relative} with section '{section}'."
        lines = _read_text(path).splitlines(keepends=True)
        target = section.strip().lower()
        section_idx = None
        for i, text_line in enumerate(lines):
            match = re.match(r"^(#+)\s+(.*?)\s*$", text_line)
            if not match:
                continue
            if section_idx is None and match.group(2).lower().rstrip(":") == target:
                section_idx = i
            elif section_idx is not None:
                insert_at = i
                while insert_at > section_idx + 1 and not lines[insert_at - 1].strip():
                    insert_at -= 1
                lines.insert(insert_at, line + "\n")
                path.write_text("".join(lines))
                return f"Appended to '{section}' in {relative}."
        if section_idx is not None:
            lines.append(line + "\n")
        else:
            lines.append(f"\n## {section}\n{line}\n")
        path.write_text("".join(lines))
        return f"Appended to '{section}' in {relative}."

    # --- To-try/Culture.md (NYC Culture Shortlist picks) ---

    def read_culture_note(self):
        """Full text of To-try/Culture.md ('' if missing), or None when the
        vault is unavailable."""
        if not self.available():
            return None
        path = self._resolve(CULTURE_LIST)
        return _read_text(path) if path.is_file() else ""

    def append_culture_lines(self, lines):
        """Append lines to the END of To-try/Culture.md. Append-only: existing
        lines (hand edits included) are never rewritten or reordered; the
        caller dedupes. Creates the note if missing. Returns a status."""
        if not self.available():
            return self._unavailable_message()
        lines = [l.rstrip("\n") for l in lines if l.strip()]
        bad = [l for l in lines if "\n" in l or not l.startswith("- ")]
        if bad:
            return f"Refused: not single '- ' lines: {bad[:1]}"
        if not lines:
            return "Nothing to append."
        path = self._resolve(CULTURE_LIST)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = _read_text(path) if path.is_file() else ""
        prefix = "\n" if existing and not existing.endswith("\n") else ""
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(prefix + "\n".join(lines) + "\n")
        return f"Appended {len(lines)} line(s) to {CULTURE_LIST}."

    # --- Daily notes ---

    def create_daily_note(self, date_str):
        """Create Daily/<date>.md from Templates/Daily.md if it is missing.

        Never overwrites an existing note. Returns True only when a note was
        created; False when it already existed, the vault is unavailable, or
        the template is missing (nothing is written without the template).
        """
        if not self.available():
            return False
        path = self._resolve(f"{DAILY_DIR}/{date_str}.md")
        if path.exists():
            return False
        template = self._resolve(DAILY_TEMPLATE)
        if not template.is_file():
            return False
        body = _TEMPLATE_DATE_RE.sub(date_str, _read_text(template))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # "x" mode: if another writer (Cowork, a phone sync) created the
            # note a moment ago, leave theirs alone.
            with open(path, "x") as handle:
                handle.write(body)
        except FileExistsError:
            return False
        return True

    def ensure_daily_notes(self, today, lookback_days=14):
        """Create any missing daily notes from today-lookback through today.

        Mirrors the Cowork daily-note-create task (template-based, never
        overwrites) so notes exist even when that task does not run.
        `today` is a date. Returns the list of date strings created.
        """
        created = []
        for offset in range(lookback_days, -1, -1):
            date_str = (today - timedelta(days=offset)).isoformat()
            if self.create_daily_note(date_str):
                created.append(date_str)
        return created

    def list_files_with_age(self, subpath="", limit=400):
        """Like list_files, plus days since each file was last modified."""
        now = datetime.now().timestamp()
        rows = []
        for rel in self.list_files(subpath, limit=limit):
            try:
                age = (now - self._resolve(rel).stat().st_mtime) / 86400
            except OSError:
                age = None
            rows.append((rel, None if age is None else int(age)))
        return rows

    def append_section(self, relative, heading, body):
        """Append a new '## heading' block to the end of a note.

        Append-only and idempotent: refuses when a heading with that exact
        text is already in the note, so a re-run never duplicates a section.
        A missing daily note is created from the template first.
        """
        if not self.available():
            return self._unavailable_message()
        if not relative.endswith(".md"):
            return "Can only append to .md notes."
        daily = _DAILY_NOTE_RE.match(relative)
        if daily:
            self.create_daily_note(daily.group(1))
        path = self._resolve(relative)
        heading = heading.strip().lstrip("#").strip()
        text = _read_text(path) if path.is_file() else ""
        if re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, re.M):
            return f"Section '{heading}' already exists in {relative}; nothing written."
        block = f"## {heading}\n{body.strip()}\n"
        text = text.rstrip("\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((text + "\n\n" if text else "") + block)
        return f"Added section '{heading}' to {relative}."

    # --- Reading queue ---

    def queue_urls(self):
        """Return the set of http(s) URLs already in Reading/queue.md."""
        if not self.available():
            return set()
        path = self._resolve(READING_QUEUE)
        if not path.is_file():
            return set()
        return {_clean_url(u) for u in _URL_RE.findall(_read_text(path))}

    def add_queue_sweep(self, heading, items):
        """Insert a sweep subsection into Reading/queue.md's Inbox section.

        `heading` is the subsection title (e.g. 'Gmail sweep (2026-09-28)');
        `items` are full '- [ ] ...' lines. The subsection goes ABOVE the
        previous sweep (newest first). If a subsection with this heading
        already exists, the items are added under it instead. Lines whose
        URL is already in the queue are skipped. Returns a status message.
        """
        if not self.available():
            return self._unavailable_message()
        path = self._resolve(READING_QUEUE)
        if not path.is_file():
            return f"{READING_QUEUE} not found in vault."
        existing = self.queue_urls()
        fresh, dupes = [], 0
        for item in items:
            item = item.rstrip()
            urls = [_clean_url(u) for u in _URL_RE.findall(item)]
            if urls and all(u in existing for u in urls):
                dupes += 1
                continue
            existing.update(urls)
            fresh.append(item)
        if not fresh:
            return f"Nothing new to add ({dupes} already in the queue)."
        lines = _read_text(path).splitlines()
        title = "### " + heading.strip().lstrip("#").strip()
        block = [title] + fresh
        if title in lines:
            at = lines.index(title) + 1
            while at < len(lines) and lines[at].startswith("- "):
                at += 1
            lines[at:at] = fresh
        else:
            inbox = next(
                (i for i, l in enumerate(lines) if re.match(r"^##\s+Inbox\b", l)), None
            )
            if inbox is None:
                lines += ["", "## Inbox (raw drops)"] + block
            else:
                at = len(lines)
                for i in range(inbox + 1, len(lines)):
                    if lines[i].startswith("### ") or re.match(r"^#{1,2}\s", lines[i]):
                        at = i
                        break
                if at == len(lines) or lines[at].startswith("## ") or lines[at].startswith("# "):
                    # No earlier sweep: end of the Inbox section.
                    while at > inbox + 1 and not lines[at - 1].strip():
                        at -= 1
                    lines[at:at] = [""] + block + [""]
                else:
                    lines[at:at] = block + [""]
        path.write_text("\n".join(lines) + "\n")
        return f"Added {len(fresh)} item(s) under '{title[4:]}' ({dupes} already in the queue)."


    def append_reading_item(self, url, title, source="telegram"):
        """Add a capture to the queue's Inbox section, deduped by URL."""
        if not self.available():
            return self._unavailable_message()
        path = self._resolve(READING_QUEUE)
        if not path.is_file():
            return f"{READING_QUEUE} not found in vault."
        text = _read_text(path)
        if url and url in text:
            return f"Already in queue: {url}"
        today = datetime.now().strftime("%Y-%m-%d")
        header = f"### Telegram capture ({today})"
        entry = f"- [ ] **{title}** — {url} _(saved {today}, {source})_"
        if header in text:
            text = text.replace(header, f"{header}\n{entry}", 1)
        else:
            block = f"{header}\n{entry}\n"
            text = _insert_in_section(text, r"^## Inbox", block)
        path.write_text(text)
        return f"Captured to reading queue: {title}"


    # --- Clip notes (Reading/clips/) ---

    def clip_urls(self):
        """Return {url: relative_path} for every clip note's frontmatter url."""
        found = {}
        for rel in self.list_files(CLIPS_DIR, limit=5000):
            meta = self.note_frontmatter(rel)
            url = meta.get("url")
            if url:
                found[_clean_url(url)] = rel
        return found

    def note_frontmatter(self, relative):
        """Return a note's YAML-ish frontmatter as a flat {key: str} dict.

        Only simple `key: value` lines are parsed (values keep their raw
        text, so a list stays as its bracketed string). Missing note or no
        frontmatter gives {}.
        """
        if not self.available():
            return {}
        path = self._resolve(relative)
        if not path.is_file():
            return {}
        return _parse_frontmatter(_read_text(path))

    def write_clip_note(self, stem, body):
        """Create Reading/clips/<stem>.md; never overwrites an existing note.

        Args:
            stem: Desired filename without extension (sanitized here).
            body: Full note text including frontmatter.

        Returns:
            The vault-relative path written (a numeric suffix is added when
            the name is taken), or an error message when unavailable.
        """
        if not self.available():
            return self._unavailable_message()
        folder = self._resolve(CLIPS_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        readme = folder / "README.md"
        if not readme.exists():
            readme.write_text(CLIPS_README)
        stem = safe_filename(stem)
        candidate, n = stem, 2
        while (folder / f"{candidate}.md").exists():
            candidate = f"{stem} ({n})"
            n += 1
        (folder / f"{candidate}.md").write_text(body.rstrip("\n") + "\n")
        return f"{CLIPS_DIR}/{candidate}.md"

    def read_template(self, relative):
        """Return a template's text, or '' when missing."""
        if not self.available():
            return ""
        path = self._resolve(relative)
        return _read_text(path) if path.is_file() else ""

    def write_note(self, relative, text):
        """Write a whole note (create or replace). Used only for notes the
        bot owns outright (the AI radar); everything else is append-only."""
        if not self.available():
            return self._unavailable_message()
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip("\n") + "\n")
        return f"Wrote {relative}."

    def create_project(self, name, index_body):
        """Create Projects/<name>/index.md. Refuses if the folder exists.

        Returns the vault-relative index path, or an error message.
        """
        if not self.available():
            return self._unavailable_message()
        name = safe_filename(name)
        if not name:
            return "Error: empty project name."
        folder = self._resolve(f"{PROJECTS_DIR}/{name}")
        if folder.exists():
            return f"Error: {PROJECTS_DIR}/{name}/ already exists."
        folder.mkdir(parents=True)
        (folder / "index.md").write_text(index_body.rstrip("\n") + "\n")
        return f"{PROJECTS_DIR}/{name}/index.md"

    # --- Reading queue cleanup ---

    def archive_stale_queue_sections(self, today, days=30):
        """Move Inbox subsections older than `days` to the queue archive.

        Implements the 30-day retention rule written in Reading/queue.md.
        A subsection is a '### Heading' block inside '## Inbox'; its date is
        the first YYYY-MM-DD in the heading. Undated subsections stay. Moved
        blocks are appended verbatim under a new '## Moved <today> ...'
        heading in Archive/Reading queue archive.md, so nothing is lost.

        Args:
            today: A date; the cutoff is today - days.
            days: Retention window in days.

        Returns:
            (sections_moved, items_moved, cutoff_iso).
        """
        if not self.available():
            return 0, 0, None
        cutoff = (today - timedelta(days=days)).isoformat()
        path = self._resolve(READING_QUEUE)
        if not path.is_file():
            return 0, 0, cutoff
        lines = _read_text(path).splitlines()
        start, end = _section_bounds(lines, r"^##\s+Inbox\b")
        if start is None:
            return 0, 0, cutoff
        keep, moved_blocks = lines[: start + 1], []
        for block in _split_subsections(lines[start + 1 : end]):
            heading = block[0] if block and block[0].startswith("### ") else ""
            found = _DATE_RE.search(heading)
            if found and found.group(0) <= cutoff:
                moved_blocks.append(block)
            else:
                keep.extend(block)
        if not moved_blocks:
            return 0, 0, cutoff
        keep.extend(lines[end:])
        items = sum(1 for b in moved_blocks for l in b if l.startswith("- ["))
        archive = self._resolve(QUEUE_ARCHIVE)
        header = (
            "# Reading queue — archived inbox sections\n\n"
            "Aged out of `Reading/queue.md` per the 30-day retention rule (see "
            "its Capture flow). Nothing deleted — promote anything here that "
            "still matters.\n"
        )
        text = _read_text(archive) if archive.is_file() else header
        block_text = "\n".join("\n".join(_strip_blank_edges(b)) for b in moved_blocks)
        text = (
            text.rstrip("\n")
            + f"\n\n## Moved {today.isoformat()} (sections dated ≤ {cutoff})\n\n"
            + block_text + "\n"
        )
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(text)
        path.write_text("\n".join(keep).rstrip("\n") + "\n")
        return len(moved_blocks), items, cutoff

    def promote_queue_items(self, section, urls):
        """Move Inbox items whose URL is in `urls` into a '## <section>'.

        The section is created at the end of the Inbox region (where the
        queue's own note says new theme sections go) when it does not exist.
        Item lines keep their text; indented continuation lines travel with
        them. A subsection left with no items loses its heading.

        Returns a status message with counts.
        """
        if not self.available():
            return self._unavailable_message()
        section = section.strip().lstrip("#").strip()
        if not section:
            return "Error: empty section name."
        wanted = {_clean_url(u) for u in urls if u}
        path = self._resolve(READING_QUEUE)
        if not path.is_file():
            return f"{READING_QUEUE} not found in vault."
        lines = _read_text(path).splitlines()
        start, end = _section_bounds(lines, r"^##\s+Inbox\b")
        if start is None:
            return "No '## Inbox' section in the queue."
        kept, moved = [lines[start]], []
        for block in _split_subsections(lines[start + 1 : end]):
            remaining, i = [], 0
            while i < len(block):
                line = block[i]
                item = [line]
                i += 1
                while i < len(block) and block[i].startswith((" ", "\t")) and block[i].strip():
                    item.append(block[i])
                    i += 1
                line_urls = {_clean_url(u) for u in _URL_RE.findall(line)}
                if line.startswith("- [") and line_urls and line_urls & wanted:
                    moved.extend(item)
                else:
                    remaining.extend(item)
            has_items = any(l.startswith("- [") for l in remaining)
            if remaining and remaining[0].startswith("### ") and not has_items:
                continue  # emptied subsection: drop its heading
            kept.extend(remaining)
        if not moved:
            return f"No Inbox items matched those URLs; nothing moved to '{section}'."
        rest = lines[end:]
        sec_start, sec_end = _section_bounds(rest, rf"^##\s+{re.escape(section)}\s*$")
        if sec_start is not None:
            insert_at = sec_end
            while insert_at > sec_start + 1 and not rest[insert_at - 1].strip():
                insert_at -= 1
            rest[insert_at:insert_at] = moved
            new_lines = lines[:start] + kept + rest
            where = "existing"
        else:
            new_lines = lines[:start] + _strip_blank_edges(kept) + ["", f"## {section}"] + moved + [""] + rest
            where = "new"
        path.write_text("\n".join(new_lines).rstrip("\n") + "\n")
        count = sum(1 for l in moved if l.startswith("- ["))
        return f"Moved {count} item(s) into {where} section '## {section}'."

    # --- Tasks ---

    def open_tasks(self):
        """Return unchecked '- [ ]' lines from Tasks/Master.md."""
        if not self.available():
            return []
        path = self._resolve(TASKS_MASTER)
        if not path.is_file():
            return []
        return [
            line.strip()[6:].strip()
            for line in _read_text(path).splitlines()
            if line.strip().startswith("- [ ]")
        ]

    def complete_task(self, task_text):
        """Check the checkbox whose text contains task_text. True if found."""
        if not self.available():
            return False
        path = self._resolve(TASKS_MASTER)
        if not path.is_file():
            return False
        lines = _read_text(path).splitlines(keepends=True)
        needle = task_text.strip().lower()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("- [ ]") and needle in stripped.lower():
                lines[i] = line.replace("- [ ]", "- [x]", 1)
                path.write_text("".join(lines))
                return True
        return False

    # --- Habit grid ---

    def upsert_habit_row(self, date_str, values):
        """Fill cells for one date row in the month's habit table.

        values maps column names (as in the table header) to cell strings.
        Existing non-empty cells are only overwritten when a new value is
        provided. A missing month file is created from the previous month's
        table format, and a missing date row is inserted in date order.
        Returns a status message.
        """
        if not self.available():
            return self._unavailable_message()
        with _HABIT_WRITE_LOCK:
            return self._upsert_habit_row_locked(date_str, values)

    def _upsert_habit_row_locked(self, date_str, values):
        """Body of upsert_habit_row; caller holds _HABIT_WRITE_LOCK."""
        month = date_str[:7]
        month_file = f"{HABITS_DIR}/{month}.md"
        path = self._resolve(month_file)
        created_note = ""
        if not path.is_file():
            if not self._create_habit_month(month):
                return (
                    f"Habit file not found: {month_file}, and no earlier "
                    f"month file exists in {HABITS_DIR}/ to copy the table "
                    "format from."
                )
            created_note = f" (created {month_file} for the new month)"
        lines = _read_text(path).splitlines(keepends=True)
        columns = _find_table_columns(lines)
        if not columns:
            return f"No habit table header found in {month_file}."
        row_idx = _find_or_insert_row(lines, columns, date_str)
        merged = _merge_cells(columns, _split_row(lines[row_idx]), values)
        lines[row_idx] = "| " + " | ".join(merged) + " |\n"
        path.write_text("".join(lines))
        saved = {k: v for k, v in values.items() if v != "" and k in columns}
        filled = ", ".join(f"{k}={v}" for k, v in saved.items())
        message = f"Updated {date_str} in {month_file}: {filled}{created_note}"
        unmatched = [k for k in values if k not in columns]
        if unmatched:
            message += (
                f" WARNING: NOT saved — the table has no column(s) named "
                f"{', '.join(unmatched)} (its columns are: "
                f"{', '.join(columns[1:])}). Tell the user about this "
                "mismatch."
            )
        return message

    def _create_habit_month(self, month):
        """Create the month's grid file with a blank row for every day.

        The table header and separator are copied from the newest earlier
        month file so custom columns carry over. Returns True on success,
        False when no earlier month grid exists to copy from.
        """
        habits_dir = self._resolve(HABITS_DIR)
        if not habits_dir.is_dir():
            return False
        earlier = sorted(
            p for p in habits_dir.glob("*.md")
            if re.fullmatch(r"\d{4}-\d{2}", p.stem) and p.stem < month
        )
        if not earlier:
            return False
        prev = earlier[-1]
        prev_lines = _read_text(prev).splitlines()
        header = separator = None
        for i, line in enumerate(prev_lines):
            if line.strip().startswith("| Date"):
                header = line.rstrip("\n")
                if i + 1 < len(prev_lines) and set(prev_lines[i + 1].strip()) <= set("|-: "):
                    separator = prev_lines[i + 1].rstrip("\n")
                break
        if not header:
            return False
        columns = _split_row(header)
        if not separator:
            separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        year, mon = (int(x) for x in month.split("-"))
        days = calendar.monthrange(year, mon)[1]
        rows = "".join(
            "| " + " | ".join([f"{month}-{day:02d}"] + [""] * (len(columns) - 1)) + " |\n"
            for day in range(1, days + 1)
        )
        title = f"# {month}"
        if prev_lines and prev_lines[0].startswith("#"):
            # Retitle both spellings: "2026-08" and "August 2026".
            prev_name = datetime.strptime(prev.stem, "%Y-%m").strftime("%B %Y")
            new_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            title = prev_lines[0].replace(prev.stem, month).replace(prev_name, new_name)
        path = self._resolve(f"{HABITS_DIR}/{month}.md")
        path.write_text(f"{title}\n\n{header}\n{separator}\n{rows}")
        return True


def _read_text(path):
    """Read a file, pulling it back from iCloud first if it was evicted.

    The vault lives in iCloud Drive with "Optimize Mac Storage" on. A
    launchd-run process cannot fault an evicted ("dataless") file back in;
    the read fails with EDEADLK ("Resource deadlock avoided"). `brctl
    download` can, so on that error ask for the file and retry briefly.
    """
    path = Path(path)
    for attempt in range(20):
        try:
            return path.read_text()
        except OSError as exc:
            if exc.errno != errno.EDEADLK or attempt == 19:
                raise
            if attempt == 0:
                subprocess.run(["brctl", "download", str(path)], capture_output=True)
            time.sleep(1)
    return path.read_text()


_URL_RE = re.compile(r"https?://[^\s)>\]\"'`]+")


def _clean_url(url):
    """Trim trailing punctuation so 'x.com/a.' and 'x.com/a' match."""
    return url.rstrip(".,;:!?*_")


def _insert_in_section(text, heading_pattern, block):
    """Insert block at the end of the section opened by heading_pattern."""
    lines = text.splitlines(keepends=True)
    in_section = False
    for i, line in enumerate(lines):
        if re.match(heading_pattern, line):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            lines.insert(i, block + "\n")
            return "".join(lines)
    if in_section:
        lines.append("\n" + block)
    else:
        lines.append(f"\n## Inbox (raw drops)\n\n{block}")
    return "".join(lines)


def _find_or_insert_row(lines, columns, date_str):
    """Return the index of date_str's row, inserting a blank one if missing.

    A missing row goes in date order among the existing date rows, or right
    after the header separator when the table has no rows yet. Mutates lines.
    """
    insert_at = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if insert_at is None:
            if stripped.startswith("| Date"):
                insert_at = i + 2
            continue
        match = re.match(r"\|\s*(\d{4}-\d{2}-\d{2})", stripped)
        if not match:
            continue
        if match.group(1) == date_str:
            return i
        if match.group(1) < date_str:
            insert_at = i + 1
    row = "| " + " | ".join([date_str] + [""] * (len(columns) - 1)) + " |\n"
    lines.insert(insert_at, row)
    return min(insert_at, len(lines) - 1)


def _find_table_columns(lines):
    """Return the habit table's column names from its header row."""
    for line in lines:
        if line.strip().startswith("| Date"):
            return _split_row(line)
    return None


def _split_row(line):
    """Split a markdown table row into stripped cell strings."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _merge_cells(columns, cells, values):
    """Overlay provided values onto existing cells, column by column."""
    cells = cells + [""] * (len(columns) - len(cells))
    merged = []
    for idx, col in enumerate(columns):
        new = values.get(col, "")
        merged.append(new if new != "" else cells[idx])
    return merged


def safe_filename(name):
    """Strip characters Obsidian/macOS reject from a note or folder name."""
    name = _FILENAME_BAD_RE.sub(" ", name or "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:90]


def _parse_frontmatter(text):
    """Parse leading '---' frontmatter into {key: raw value string}."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def _section_bounds(lines, heading_pattern):
    """Return (start, end) of the '## ' section whose heading matches.

    `start` is the heading line's index; `end` is the index of the next
    '## '/'# ' heading (or len(lines)). (None, None) when not found.
    """
    start = next((i for i, l in enumerate(lines) if re.match(heading_pattern, l)), None)
    if start is None:
        return None, None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{1,2}\s", lines[i]):
            end = i
            break
    return start, end


def _split_subsections(lines):
    """Split a section body into blocks: a leading preamble (no heading)
    followed by one block per '### ' heading, each including its lines up
    to the next heading."""
    blocks, current = [], []
    for line in lines:
        if line.startswith("### "):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _strip_blank_edges(block):
    """Drop leading/trailing blank lines from a list of lines."""
    lines = list(block)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines
