"""JSON-file persistence for conversation history and reminders.

State lives in ~/Library/Application Support/agent-team/ — deliberately OUTSIDE
the repo, because the repo sits in iCloud-synced ~/Documents. iCloud's "Optimize
Mac Storage" evicts idle files to dataless placeholders, and launchd cannot
rematerialize them at spawn time, which crash-looped the bot with EX_CONFIG.
~/Library is not iCloud-synced, so state files stay local and materialized.
Everything is small enough that read-modify-write per operation is fine.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

DEFAULT_STATE_DIR = Path.home() / "Library" / "Application Support" / "agent-team"


class StateStore:
    """Reads and writes per-chat history and the shared reminder list."""

    def __init__(self, state_dir=None, history_limit=40):
        """Create the state directory if needed and remember limits."""
        self.state_dir = Path(state_dir) if state_dir else DEFAULT_STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.history_limit = history_limit

    def _read_json(self, path, default):
        """Read a JSON file, returning a default on absence or corruption."""
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return default

    def _write_json(self, path, data):
        """Write data to a JSON file atomically enough for a single-user bot."""
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp.replace(path)

    # --- Conversation history (shared transcript per chat) ---

    def _history_path(self, chat_id):
        """Return the history file path for one chat."""
        return self.state_dir / f"history-{chat_id}.json"

    def get_history(self, chat_id):
        """Return the recent transcript for a chat as a list of entries."""
        return self._read_json(self._history_path(chat_id), [])

    def append_history(self, chat_id, speaker, text):
        """Append a transcript entry ({speaker, text, ts}) and trim to limit."""
        history = self.get_history(chat_id)
        history.append(
            {"speaker": speaker, "text": text, "ts": datetime.now().isoformat()}
        )
        self._write_json(self._history_path(chat_id), history[-self.history_limit :])

    # --- Reminders ---

    @property
    def _reminders_path(self):
        """Return the shared reminders file path."""
        return self.state_dir / "reminders.json"

    def add_reminder(self, chat_id, persona_key, due_iso, text):
        """Store a reminder and return its short id."""
        reminders = self._read_json(self._reminders_path, [])
        reminder_id = uuid.uuid4().hex[:8]
        reminders.append(
            {
                "id": reminder_id,
                "chat_id": chat_id,
                "persona": persona_key,
                "due": due_iso,
                "text": text,
                "created": datetime.now().isoformat(),
            }
        )
        self._write_json(self._reminders_path, reminders)
        return reminder_id

    def list_reminders(self, chat_id):
        """Return pending reminders for a chat, soonest first."""
        reminders = self._read_json(self._reminders_path, [])
        mine = [r for r in reminders if r["chat_id"] == chat_id]
        return sorted(mine, key=lambda r: r["due"])

    def cancel_reminder(self, chat_id, reminder_id):
        """Delete a reminder by id. Returns True if one was removed."""
        reminders = self._read_json(self._reminders_path, [])
        kept = [
            r
            for r in reminders
            if not (r["chat_id"] == chat_id and r["id"] == reminder_id)
        ]
        if len(kept) == len(reminders):
            return False
        self._write_json(self._reminders_path, kept)
        return True

    def pop_due_reminders(self, now=None):
        """Remove and return all reminders whose due time has passed."""
        now = now or datetime.now()
        reminders = self._read_json(self._reminders_path, [])
        due, pending = [], []
        for reminder in reminders:
            try:
                is_due = datetime.fromisoformat(reminder["due"]) <= now
            except ValueError:
                is_due = True  # unparseable due date: deliver rather than strand it
            (due if is_due else pending).append(reminder)
        if due:
            self._write_json(self._reminders_path, pending)
        return due
