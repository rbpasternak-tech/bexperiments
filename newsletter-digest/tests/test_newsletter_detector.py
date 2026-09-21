"""Tests for newsletter detection and topic matching."""

import unittest

from newsletter_detector import detect_newsletters


def _email(sender="news@example.com", subject="", body="", headers=None):
    return {
        "sender": sender,
        "subject": subject,
        "body_text": body,
        "headers": headers or {},
    }


class DetectNewslettersTests(unittest.TestCase):
    """Combined newsletter + topic filtering."""

    def test_list_unsubscribe_with_keyword_matches(self):
        email = _email(
            subject="Weekly legal tech roundup",
            headers={"list-unsubscribe": "<mailto:x>"},
        )
        self.assertEqual(detect_newsletters([email], [], ["legal tech"]), [email])

    def test_plain_email_is_not_a_newsletter(self):
        email = _email(sender="friend@gmail.com", subject="legal tech chat")
        self.assertEqual(detect_newsletters([email], [], ["legal tech"]), [])

    def test_platform_sender_and_whitelist(self):
        email = _email(sender="Author <author@substack.com>", subject="Hello")
        self.assertEqual(detect_newsletters([email], ["@substack.com"], []), [email])

    def test_keyword_requires_word_boundary(self):
        email = _email(subject="Wildcard LLMs", headers={"list-id": "x"})
        self.assertEqual(detect_newsletters([email], [], ["LLM"]), [])
        email["subject"] = "Wildcard LLM release"
        self.assertEqual(detect_newsletters([email], [], ["LLM"]), [email])

    def test_precedence_bulk_header(self):
        email = _email(subject="Startup news", headers={"precedence": "Bulk"})
        self.assertEqual(detect_newsletters([email], [], ["startup"]), [email])

    def test_keyword_only_scans_start_of_body(self):
        body = "x" * 3100 + " compliance"
        email = _email(body=body, headers={"list-id": "x"})
        self.assertEqual(detect_newsletters([email], [], ["compliance"]), [])


if __name__ == "__main__":
    unittest.main()
