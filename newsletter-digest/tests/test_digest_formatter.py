"""Tests for the markdown-to-HTML digest formatter."""

import unittest

from digest_formatter import _inline_format, _markdown_to_html, format_digest_html


class InlineFormatTests(unittest.TestCase):
    """Inline bold, italic, link, and escaping behavior."""

    def test_link_and_bold(self):
        out = _inline_format("See **this** at [TechCrunch](https://tc.com/a)")
        self.assertEqual(
            out, 'See <strong>this</strong> at <a href="https://tc.com/a">TechCrunch</a>'
        )

    def test_italic_source_line(self):
        out = _inline_format("*Source: [Verge](https://v.com)*")
        self.assertEqual(out, '<em>Source: <a href="https://v.com">Verge</a></em>')

    def test_escapes_html_in_text(self):
        out = _inline_format("AI <b>beats</b> humans & more")
        self.assertEqual(out, "AI &lt;b&gt;beats&lt;/b&gt; humans &amp; more")

    def test_ampersand_in_url_is_escaped_once(self):
        out = _inline_format("[x](https://e.com/?a=1&b=2)")
        self.assertEqual(out, '<a href="https://e.com/?a=1&amp;b=2">x</a>')


class MarkdownToHtmlTests(unittest.TestCase):
    """Block-level conversion."""

    def test_headers_and_paragraphs(self):
        html = _markdown_to_html("# Title\n\n## Section\n\nSome text\n### Sub")
        self.assertIn("<h2>Title</h2>", html)
        self.assertIn("<h2>Section</h2>", html)
        self.assertIn("<p>Some text</p>", html)
        self.assertIn("<h3>Sub</h3>", html)

    def test_bullet_list_is_closed(self):
        html = _markdown_to_html("- one\n- two\n\nAfter")
        self.assertEqual(
            html, "<ul>\n<li>one</li>\n<li>two</li>\n</ul>\n\n<p>After</p>"
        )

    def test_numbered_list(self):
        html = _markdown_to_html("1. first\n2. second")
        self.assertEqual(html, "<ol>\n<li>first</li>\n<li>second</li>\n</ol>")

    def test_switching_list_types_closes_previous(self):
        html = _markdown_to_html("- a\n1. b")
        self.assertEqual(html, "<ul>\n<li>a</li>\n</ul>\n<ol>\n<li>b</li>\n</ol>")

    def test_horizontal_rule(self):
        self.assertEqual(_markdown_to_html("---"), "<hr>")

    def test_full_document_wraps_body(self):
        html = format_digest_html("## Hi\n- x", "Jan 01, 2026", "Jan 04, 2026")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("Jan 01, 2026 — Jan 04, 2026", html)
        self.assertIn("<h2>Hi</h2>", html)


if __name__ == "__main__":
    unittest.main()
