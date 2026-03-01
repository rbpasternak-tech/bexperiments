"""Extract clean readable text from HTML email bodies."""

import re

from bs4 import BeautifulSoup


def extract_text(email):
    """Extract readable text content from an email.

    Prefers HTML body (parsed to text) over plain text body.
    Strips navigation, footers, unsubscribe blocks, and excessive whitespace.

    Args:
        email: Email dict from gmail_client with body_html and body_text fields.

    Returns:
        Cleaned text string of the email content.
    """
    html = email.get("body_html", "")
    if html:
        return _html_to_text(html)

    text = email.get("body_text", "")
    if text:
        return _clean_text(text)

    return ""


def _html_to_text(html):
    """Convert HTML email body to clean readable text."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that aren't content
    for tag in soup.find_all(["script", "style", "head", "nav", "footer"]):
        tag.decompose()

    # Remove common newsletter footer/unsubscribe blocks
    unsubscribe_pattern = re.compile(
        r"(unsubscribe|manage preferences|update your preferences|view in browser|"
        r"email preferences|opt.out|privacy policy|terms of service)",
        re.IGNORECASE,
    )
    for tag in soup.find_all(string=unsubscribe_pattern):
        # Walk up the tree manually to find a container element to remove
        node = tag
        while node:
            node = getattr(node, "parent", None)
            if node and node.name in ("div", "p", "td", "tr", "table", "section"):
                node.decompose()
                break

    text = soup.get_text(separator="\n")
    return _clean_text(text)


def _clean_text(text):
    """Clean up extracted text: normalize whitespace, remove junk."""
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Strip each line
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    # Remove leading/trailing whitespace
    text = text.strip()

    # Truncate very long emails to avoid blowing up the summarizer context
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Content truncated...]"

    return text
