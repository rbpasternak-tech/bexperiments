"""Detect and filter newsletter emails related to tech and legal tech."""

import re


def detect_newsletters(emails, sender_whitelist, keywords):
    """Filter emails to only those that are newsletters matching tech/legal-tech topics.

    Args:
        emails: List of email dicts from gmail_client.fetch_emails().
        sender_whitelist: List of sender patterns to match (e.g., "@substack.com").
        keywords: List of keywords to look for in subject/body.

    Returns:
        List of email dicts that are detected as relevant newsletters.
    """
    results = []
    for email in emails:
        if _is_newsletter(email) and _matches_topic(email, sender_whitelist, keywords):
            results.append(email)
    return results


def _is_newsletter(email):
    """Check if an email is likely a newsletter based on headers and sender patterns."""
    headers = email.get("headers", {})

    # Strong signal: List-Unsubscribe header
    if "list-unsubscribe" in headers:
        return True

    # Check for mailing list headers
    if "list-id" in headers:
        return True

    # Check sender for known newsletter platforms
    sender = email.get("sender", "").lower()
    newsletter_platforms = [
        "@substack.com",
        "@beehiiv.com",
        "@convertkit.com",
        "@mailchimp.com",
        "@sendinblue.com",
        "@buttondown.email",
        "@revue.email",
        "@ghost.io",
        "noreply@medium.com",
        "@newsletters.",
        "newsletter@",
        "digest@",
    ]
    for platform in newsletter_platforms:
        if platform in sender:
            return True

    # Check precedence header
    precedence = headers.get("precedence", "")
    if isinstance(precedence, str) and precedence.lower() in ("bulk", "list"):
        return True

    return False


def _matches_topic(email, sender_whitelist, keywords):
    """Check if a newsletter matches tech/legal-tech topics."""
    sender = email.get("sender", "").lower()
    subject = email.get("subject", "").lower()
    body_text = email.get("body_text", "").lower()

    # Check sender whitelist first (fast path)
    for pattern in sender_whitelist:
        if pattern.lower() in sender:
            return True

    # Search subject and body for keywords
    searchable = f"{subject} {body_text[:3000]}"  # Limit body scan for performance

    for keyword in keywords:
        if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", searchable):
            return True

    return False
