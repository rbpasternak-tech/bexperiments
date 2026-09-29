"""Read-only Gmail access for the unattended inbox sweep.

Uses an OAuth token that already carries the gmail.readonly scope. The
installer copies the newsletter digest's token (which has it) to
~/Library/Application Support/agent-team/gmail_token.json, outside iCloud,
so a launchd-run bot can always read it. No browser consent ever happens
here: if the token is missing or revoked, calls raise GmailUnavailable with
the fix, and the sweep reports it instead of hanging.
"""

import base64
import html
import os
import re
from pathlib import Path

DEFAULT_TOKEN_PATH = (
    Path.home() / "Library" / "Application Support" / "agent-team" / "gmail_token.json"
)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_HREF_RE = re.compile(r"""href=["'](https?://[^"'\s>]+)""", re.I)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
# Links that are never reading material.
_JUNK_URL_RE = re.compile(
    r"unsubscribe|/optout|opt-out|manage[-_]?preferences|email[-_]?preferences|"
    r"list-manage\.com/(?:un|profile)|\.(?:png|jpe?g|gif)(?:\?|$)|"
    r"/open\?|/o\.gif|pixel|beacon|w3\.org|schemas\.",
    re.I,
)


class GmailUnavailable(RuntimeError):
    """Gmail cannot be used unattended right now; the message says why."""


class GmailReader:
    """Minimal read-only Gmail client (search + message text)."""

    def __init__(self, token_path=None):
        """Remember the token location; the API client is built lazily."""
        self.token_path = Path(os.path.expanduser(str(token_path or DEFAULT_TOKEN_PATH)))
        self._service = None

    def _get_service(self):
        """Build the Gmail service from the saved token, refreshing it."""
        if self._service:
            return self._service
        try:
            from google.auth.exceptions import RefreshError
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GmailUnavailable(
                f"Google API libraries missing ({exc}); re-run agent-team/install-launchd.sh"
            ) from exc
        if not self.token_path.is_file():
            raise GmailUnavailable(
                f"no Gmail token at {self.token_path}; re-run "
                "agent-team/install-launchd.sh (it copies the newsletter "
                "digest's token)"
            )
        creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if not creds.valid:
            if not creds.refresh_token:
                raise GmailUnavailable("Gmail token has no refresh token")
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise GmailUnavailable(
                    f"Gmail token refresh failed ({exc}). Re-consent by running "
                    "the newsletter digest from Terminal, then re-run "
                    "agent-team/install-launchd.sh"
                ) from exc
            tmp = self.token_path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(creds.to_json())
            os.replace(tmp, self.token_path)
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def search(self, query, max_results=50):
        """Return messages matching a Gmail query, newest first.

        Each item: id, date, from, to, subject, snippet, urls (up to 8
        candidate reading links from the body), permalink.
        """
        service = self._get_service()
        max_results = max(1, min(int(max_results), 150))
        ids, page = [], None
        while len(ids) < max_results:
            resp = service.users().messages().list(
                userId="me", q=query, maxResults=min(100, max_results - len(ids)),
                pageToken=page,
            ).execute()
            ids += [m["id"] for m in resp.get("messages", [])]
            page = resp.get("nextPageToken")
            if not page:
                break
        return [self._summarize(service, mid) for mid in ids]

    def read(self, message_id, max_chars=6000):
        """Return a message's plain text (HTML stripped), truncated."""
        service = self._get_service()
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        plain, html_body = _bodies(msg.get("payload", {}))
        text = plain or _strip_html(html_body)
        headers = _headers(msg)
        head = f"From: {headers.get('from', '')}\nSubject: {headers.get('subject', '')}\nDate: {headers.get('date', '')}\n\n"
        text = head + text.strip()
        return text if len(text) <= max_chars else text[:max_chars] + "\n[... truncated ...]"

    def _summarize(self, service, message_id):
        """Fetch one message and reduce it to the fields the sweep needs."""
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = _headers(msg)
        plain, html_body = _bodies(msg.get("payload", {}))
        urls = []
        for url in _HREF_RE.findall(html_body) + _URL_RE.findall(plain):
            url = html.unescape(url).rstrip(".,;:!?")
            if not _JUNK_URL_RE.search(url) and url not in urls:
                urls.append(url)
        return {
            "id": message_id,
            "date": headers.get("date", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "snippet": html.unescape(msg.get("snippet", "")),
            "unread": "UNREAD" in msg.get("labelIds", []),
            "urls": urls[:8],
            "permalink": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
        }


def _headers(msg):
    """Lower-cased header dict for a Gmail message resource."""
    return {
        h["name"].lower(): h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }


def _bodies(payload):
    """Return (plain_text, html) decoded from a message payload tree."""
    plain, html_parts = [], []

    def walk(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime in ("text/plain", "text/html"):
            decoded = base64.urlsafe_b64decode(data + "===").decode("utf-8", "replace")
            (plain if mime == "text/plain" else html_parts).append(decoded)
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return "\n".join(plain), "\n".join(html_parts)


def _strip_html(text):
    """Crude HTML-to-text for reading a message body."""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text))
