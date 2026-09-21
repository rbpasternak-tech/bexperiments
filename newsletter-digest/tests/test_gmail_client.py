"""Tests for Gmail message parsing (no network)."""

import base64
import unittest

try:
    from gmail_client import _parse_message
except BaseException as exc:  # noqa: B036 - native-library panics are not Exception subclasses
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise
    _parse_message = None
    IMPORT_ERROR = repr(exc)


def _b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode()


@unittest.skipIf(_parse_message is None, "gmail_client dependencies unavailable")
class ParseMessageTests(unittest.TestCase):
    """Header collection and multipart body extraction."""

    def test_multipart_message(self):
        msg = {
            "id": "abc",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "A <a@x.com>"},
                    {"name": "Subject", "value": "Hi"},
                    {"name": "Received", "value": "one"},
                    {"name": "Received", "value": "two"},
                ],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64("plain")}},
                    {
                        "mimeType": "multipart/related",
                        "parts": [
                            {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}}
                        ],
                    },
                ],
            },
        }
        parsed = _parse_message(msg)
        self.assertEqual(parsed["id"], "abc")
        self.assertEqual(parsed["sender"], "A <a@x.com>")
        self.assertEqual(parsed["subject"], "Hi")
        self.assertEqual(parsed["headers"]["received"], ["one", "two"])
        self.assertEqual(parsed["body_text"], "plain")
        self.assertEqual(parsed["body_html"], "<p>html</p>")

    def test_empty_payload(self):
        parsed = _parse_message({"id": "1"})
        self.assertEqual(parsed["body_text"], "")
        self.assertEqual(parsed["body_html"], "")
        self.assertEqual(parsed["date"], "")


if __name__ == "__main__":
    unittest.main()
