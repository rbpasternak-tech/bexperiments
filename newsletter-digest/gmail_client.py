"""Gmail API client for fetching emails and sending the digest."""

import base64
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")


def _get_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_PATH}. Download OAuth credentials from "
                    "Google Cloud Console and place them in the project directory. "
                    "See README.md for setup instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=8090)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_emails(lookback_days, max_emails=200):
    """Fetch emails from the last N days.

    Args:
        lookback_days: Number of days back to search.
        max_emails: Maximum number of emails to return.

    Returns:
        List of dicts with keys: id, sender, subject, date, headers, body_html, body_text
    """
    service = _get_service()

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
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_stub["id"], format="full")
                .execute()
            )
            results.append(_parse_message(msg))

            if len(results) >= max_emails:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


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

    body_html = ""
    body_text = ""
    _extract_body(msg.get("payload", {}), body_parts={"html": [], "text": []})
    parts_result = {"html": [], "text": []}
    _extract_body(msg.get("payload", {}), parts_result)
    body_html = "".join(parts_result["html"])
    body_text = "".join(parts_result["text"])

    return {
        "id": msg["id"],
        "sender": header_dict.get("from", ""),
        "subject": header_dict.get("subject", ""),
        "date": header_dict.get("date", ""),
        "headers": header_dict,
        "body_html": body_html,
        "body_text": body_text,
    }


def _extract_body(payload, body_parts):
    """Recursively extract body text and HTML from message payload."""
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            body_parts["html"].append(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))
    elif mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            body_parts["text"].append(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))

    for part in payload.get("parts", []):
        _extract_body(part, body_parts)


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
