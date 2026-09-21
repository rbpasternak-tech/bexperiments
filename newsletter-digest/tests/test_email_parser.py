"""Tests for HTML email text extraction."""

import unittest

from email_parser import extract_text


class ExtractTextTests(unittest.TestCase):
    """HTML cleanup and plain-text fallback."""

    def test_prefers_html_and_strips_tags(self):
        email = {
            "body_html": "<html><head><style>p{}</style></head><body>"
            "<p>Hello   <b>world</b></p><script>x()</script></body></html>",
            "body_text": "ignored",
        }
        self.assertEqual(extract_text(email), "Hello\nworld")

    def test_removes_unsubscribe_block(self):
        email = {
            "body_html": "<div><p>Real content</p></div>"
            "<div><p>Click here to unsubscribe from this list</p></div>"
        }
        text = extract_text(email)
        self.assertIn("Real content", text)
        self.assertNotIn("unsubscribe", text.lower())

    def test_plain_text_fallback_and_whitespace(self):
        email = {"body_html": "", "body_text": "  a  \n\n\n\n b \t\t c  "}
        self.assertEqual(extract_text(email), "a\n\nb c")

    def test_truncates_long_content(self):
        email = {"body_text": "y" * 9000}
        text = extract_text(email)
        self.assertTrue(text.endswith("[Content truncated...]"))
        self.assertLess(len(text), 8100)

    def test_empty_email(self):
        self.assertEqual(extract_text({}), "")


if __name__ == "__main__":
    unittest.main()
