"""Read/write helpers for the Obsidian vault (plain markdown files on disk).

The vault is iCloud-synced but locally it's just a folder, so the bot reads
and writes files directly. One-writer rule: this module only touches the
habit grid (Tracking/Habits/), the reading queue Inbox, and task checkboxes
in Tasks/Master.md — daily notes and review sections belong to the Cowork
scheduled tasks.
"""

import re
from datetime import datetime
from pathlib import Path

READING_QUEUE = "Reading/queue.md"
TASKS_MASTER = "Tasks/Master.md"
HABITS_DIR = "Tracking/Habits"


class Vault:
    """Filesystem access to the vault, guarded against path escapes."""

    def __init__(self, vault_path):
        """Remember the vault root; a falsy path means 'not configured'."""
        self.root = Path(vault_path).expanduser() if vault_path else None

    def available(self):
        """Return True when the vault folder exists on this machine."""
        return bool(self.root) and self.root.is_dir()

    def _resolve(self, relative):
        """Resolve a vault-relative path, refusing anything outside the root."""
        path = (self.root / relative).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError(f"Path escapes vault: {relative}")
        return path

    def read_note(self, relative, max_chars=8000):
        """Return a note's text (truncated), or an explanatory message."""
        if not self.available():
            return "Vault not available on this machine."
        path = self._resolve(relative)
        if not path.is_file():
            return f"Note not found: {relative}"
        text = path.read_text()
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
            return "Vault not available on this machine."
        if not relative.endswith(".md"):
            return "Can only append to .md notes."
        path = self._resolve(relative)
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"## {section}\n{line}\n")
            return f"Created {relative} with section '{section}'."
        lines = path.read_text().splitlines(keepends=True)
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

    # --- Reading queue ---

    def append_reading_item(self, url, title, source="telegram"):
        """Add a capture to the queue's Inbox section, deduped by URL."""
        if not self.available():
            return "Vault not available on this machine."
        path = self._resolve(READING_QUEUE)
        if not path.is_file():
            return f"{READING_QUEUE} not found in vault."
        text = path.read_text()
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
            for line in path.read_text().splitlines()
            if line.strip().startswith("- [ ]")
        ]

    def complete_task(self, task_text):
        """Check the checkbox whose text contains task_text. True if found."""
        if not self.available():
            return False
        path = self._resolve(TASKS_MASTER)
        if not path.is_file():
            return False
        lines = path.read_text().splitlines(keepends=True)
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
        provided. Returns a status message.
        """
        if not self.available():
            return "Vault not available on this machine."
        month_file = f"{HABITS_DIR}/{date_str[:7]}.md"
        path = self._resolve(month_file)
        if not path.is_file():
            return f"Habit file not found: {month_file}"
        lines = path.read_text().splitlines(keepends=True)
        columns = _find_table_columns(lines)
        if not columns:
            return f"No habit table header found in {month_file}."
        for i, line in enumerate(lines):
            if line.strip().startswith(f"| {date_str}"):
                cells = _split_row(line)
                merged = _merge_cells(columns, cells, values)
                lines[i] = "| " + " | ".join(merged) + " |\n"
                path.write_text("".join(lines))
                filled = ", ".join(f"{k}={v}" for k, v in values.items() if v != "")
                return f"Updated {date_str} in {month_file}: {filled}"
        return f"No row for {date_str} in {month_file} (add the date row first)."


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
