"""Thin wrapper around the Telegram Bot HTTP API using long polling.

No Telegram SDK — just requests against https://api.telegram.org, matching
the no-build-tools convention of this repo.
"""

import json
import os
from pathlib import Path

import requests

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LEN = 4096
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_token(config=None):
    """Load the Telegram bot token.

    Precedence: config.yaml's telegram_token (the agent team's dedicated
    bot — it cannot share a token with another poller, e.g. the Claude
    Code Telegram plugin, or Telegram returns 409 Conflict), then the
    TELEGRAM_BOT_TOKEN env var, then .claude/settings.local.json (an
    "env" map or a top-level "telegramBotToken" key). Exits with
    instructions if none is set.
    """
    token = (config or {}).get("telegram_token")
    if token:
        return token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    settings_path = REPO_ROOT / ".claude" / "settings.local.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except (OSError, json.JSONDecodeError):
            data = {}
        token = (data.get("env") or {}).get("TELEGRAM_BOT_TOKEN") or data.get(
            "telegramBotToken"
        )
        if token:
            return token
    raise SystemExit(
        "No Telegram bot token found. Set the TELEGRAM_BOT_TOKEN env var, or add\n"
        'it to .claude/settings.local.json as {"env": {"TELEGRAM_BOT_TOKEN": "..."}}.'
    )


class TelegramClient:
    """Minimal Telegram Bot API client (getUpdates long polling + sendMessage)."""

    def __init__(self, token):
        """Store the bot token and build the API base URL."""
        self.base_url = f"{API_BASE}/bot{token}"

    def _call(self, method, params, http_timeout=40):
        """POST a Bot API method and return its "result" payload."""
        response = requests.post(
            f"{self.base_url}/{method}", json=params, timeout=http_timeout
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error from {method}: {payload}")
        return payload["result"]

    def get_updates(self, offset, poll_timeout=25):
        """Long-poll for new message updates starting at the given offset."""
        return self._call(
            "getUpdates",
            {"offset": offset, "timeout": poll_timeout, "allowed_updates": ["message"]},
            http_timeout=poll_timeout + 15,
        )

    def send_message(self, chat_id, text):
        """Send a plain-text message, splitting to fit Telegram's length cap."""
        for start in range(0, max(len(text), 1), MAX_MESSAGE_LEN):
            chunk = text[start : start + MAX_MESSAGE_LEN]
            self._call("sendMessage", {"chat_id": chat_id, "text": chunk})
