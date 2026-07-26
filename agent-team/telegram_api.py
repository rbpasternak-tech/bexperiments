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


def load_local_env(name, extra_keys=()):
    """Look up a secret in .claude/settings.local.json.

    Checks the "env" map for name, then any legacy top-level keys given in
    extra_keys. Returns None if absent or unreadable.
    """
    settings_path = REPO_ROOT / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    value = (data.get("env") or {}).get(name)
    for key in extra_keys:
        value = value or data.get(key)
    return value


def load_secret(name, config=None, config_key=None, extra_keys=()):
    """Resolve a secret: config.yaml value, env var, settings.local.json."""
    value = (config or {}).get(config_key) if config_key else None
    return value or os.environ.get(name) or load_local_env(name, extra_keys)


def load_token(config=None):
    """Load the Telegram bot token.

    Precedence: config.yaml's telegram_token (the agent team's dedicated
    bot — it cannot share a token with another poller, e.g. the Claude
    Code Telegram plugin, or Telegram returns 409 Conflict), then the
    TELEGRAM_BOT_TOKEN env var, then .claude/settings.local.json (an
    "env" map or a top-level "telegramBotToken" key). Exits with
    instructions if none is set.
    """
    token = load_secret(
        "TELEGRAM_BOT_TOKEN", config, "telegram_token", ("telegramBotToken",)
    )
    if token:
        return token
    raise SystemExit(
        "No Telegram bot token found. Set telegram_token in config.yaml, the\n"
        "TELEGRAM_BOT_TOKEN env var, or .claude/settings.local.json as\n"
        '{"env": {"TELEGRAM_BOT_TOKEN": "..."}}.'
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
