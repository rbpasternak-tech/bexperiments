"""Read/write helpers for the Obsidian vault (plain markdown files on disk).

The vault is iCloud-synced but locally it's just a folder, so the bot reads
and writes files directly. One-writer rule: this module only touches the
habit grid (Tracking/Habits/), the reading queue Inbox, and task checkboxes
in Tasks/Master.md — daily notes and review sections belong to the Cowork
scheduled tasks.
"""

import calendar
import os
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
        if not str(path).startswith(str(self.root.resolve())):
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
        lines = path.read_text().splitlines()
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
            return self._unavailable_message()
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
            return self._unavailable_message()
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
        provided. A missing month file is created from the previous month's
        table format, and a missing date row is inserted in date order.
        Returns a status message.
        """
        if not self.available():
            return self._unavailable_message()
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
        lines = path.read_text().splitlines(keepends=True)
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
        prev_lines = prev.read_text().splitlines()
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
            title = prev_lines[0].replace(prev.stem, month)
        path = self._resolve(f"{HABITS_DIR}/{month}.md")
        path.write_text(f"{title}\n\n{header}\n{separator}\n{rows}")
        return True


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
