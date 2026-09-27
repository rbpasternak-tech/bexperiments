"""Gmail API client for fetching emails and sending the digest."""

import base64
import os
import re
import socket
import sys
import time
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")


def _get_service():
    """Authenticate and return a Gmail API service instance.

    Raises:
        FileNotFoundError: credentials.json is missing and a new consent is needed.
        RuntimeError: a new browser consent is needed but there is no terminal
            (for example under launchd), where it would hang forever.
    """
    creds = None

    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except (ValueError, OSError) as e:
            print(f"  Warning: could not read {TOKEN_PATH} ({e}); a new consent is needed.")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                print(f"  Warning: Gmail token refresh failed ({e}); a new consent is needed.")
                creds = None
        if not creds or not creds.valid:
            creds = _run_consent_flow()

        _write_token(creds.to_json())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _run_consent_flow():
    """Run the interactive browser OAuth consent and return credentials."""
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Missing {CREDENTIALS_PATH}. Download OAuth credentials from "
            "Google Cloud Console and place them in the project directory. "
            "See SETUP.md for setup instructions."
        )
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Gmail needs a new OAuth consent, which requires a browser and a "
            "terminal. Run the wrapper once from Terminal: "
            "~/Library/Application\\ Support/newsletter-digest/run.sh --dry-run --skip-trends"
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    return flow.run_local_server(port=8090)


def _write_token(token_json):
    """Write token.json atomically with owner-only permissions."""
    tmp_path = TOKEN_PATH + ".tmp"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as token_file:
        token_file.write(token_json)
    os.replace(tmp_path, TOKEN_PATH)


def fetch_emails(lookback_days, max_emails=200, after_date=None, before_date=None):
    """Fetch emails from the last N days, or an explicit date range.

    Args:
        lookback_days: Number of days back to search (used when after_date is None).
        max_emails: Maximum number of emails to return.
        after_date: datetime — if set, fetch emails on/after this date.
        before_date: datetime — if set, fetch emails up to/before this date.

    Returns:
        List of dicts with keys: id, sender, subject, date, headers, body_html, body_text
    """
    service = _get_service()

    if after_date and before_date:
        # Gmail date format: YYYY/MM/DD
        after_str = after_date.strftime("%Y/%m/%d")
        before_str = (before_date + timedelta(days=1)).strftime("%Y/%m/%d")
        query = f"after:{after_str} before:{before_str}"
    else:
        query = f"newer_than:{lookback_days}d"
    results = []
    page_token = None

    while len(results) < max_emails:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(100, max_emails - len(results)),
                pageToken=page_token,
            )
            .execute()
        )

        messages = response.get("messages", [])
        if not messages:
            break

        for msg_stub in messages:
            msg = _fetch_message_with_retry(service, msg_stub["id"])
            results.append(_parse_message(msg))

            if len(results) >= max_emails:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def _fetch_message_with_retry(service, message_id, max_attempts=3):
    """Fetch a single Gmail message, backing off on 429/5xx and network errors."""
    for attempt in range(max_attempts):
        try:
            return (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except HttpError as e:
            status = e.resp.status
            if (status == 429 or status >= 500) and attempt < max_attempts - 1:
                wait = 2 ** attempt
                print(f"  Gmail API error {status} for message {message_id} "
                      f"(attempt {attempt + 1}/{max_attempts}), retrying in {wait}s")
                time.sleep(wait)
            else:
                raise
        except (socket.timeout, ConnectionError) as e:
            if attempt < max_attempts - 1:
                wait = 2 ** attempt
                print(f"  Network error for message {message_id} ({e}), retrying in {wait}s")
                time.sleep(wait)
            else:
                raise
    return None  # unreachable


def _parse_message(msg):
    """Parse a Gmail API message into a structured dict."""
    headers = msg.get("payload", {}).get("headers", [])
    header_dict = {}
    for h in headers:
        name = h["name"].lower()
        if name in header_dict:
            if isinstance(header_dict[name], list):
                header_dict[name].append(h["value"])
            else:
                header_dict[name] = [header_dict[name], h["value"]]
        else:
            header_dict[name] = h["value"]

    parts_result = {"html": [], "text": []}
    _extract_body(msg.get("payload", {}), parts_result)
    body_html = "".join(parts_result["html"])
    body_text = "".join(parts_result["text"])

    def first(name):
        value = header_dict.get(name, "")
        return value[0] if isinstance(value, list) else value

    return {
        "id": msg["id"],
        "sender": first("from"),
        "subject": first("subject"),
        "date": first("date"),
        "headers": header_dict,
        "body_html": body_html,
        "body_text": body_text,
    }


def _extract_body(payload, body_parts):
    """Recursively extract body text and HTML from message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type in ("text/html", "text/plain"):
        data = payload.get("body", {}).get("data", "")
        if data:
            key = "html" if mime_type == "text/html" else "text"
            body_parts[key].append(_decode_part(data, _part_charset(payload)))

    for part in payload.get("parts", []):
        _extract_body(part, body_parts)


def _part_charset(payload):
    """Return the charset declared in a MIME part's Content-Type, or utf-8."""
    for header in payload.get("headers", []):
        if header.get("name", "").lower() == "content-type":
            match = re.search(r'charset="?([\w.:-]+)"?', header.get("value", ""), re.I)
            if match:
                return match.group(1)
    return "utf-8"


def _decode_part(data, charset):
    """Decode a base64url Gmail body, falling back to utf-8 for unknown charsets."""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def send_email(recipient, subject, html_body):
    """Send an HTML email via Gmail API.

    Args:
        recipient: Email address to send to.
        subject: Email subject line.
        html_body: HTML content of the email.
    """
    service = _get_service()

    message = MIMEMultipart("alternative")
    message["to"] = recipient
    message["subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
