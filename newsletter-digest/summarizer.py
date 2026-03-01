"""Summarize collected content using the Anthropic Claude API."""

import anthropic

from email_parser import extract_text


SYSTEM_PROMPT = """\
You are a helpful assistant that creates concise, scannable email digests of tech and legal tech news.

You will receive two types of content:
1. Newsletter emails the user subscribes to
2. Recent articles from RSS feeds (tech and legal tech news sites)

Your job is to synthesize all of this into a single well-organized digest. Follow these rules:

- Group content by THEME, not by source. Use clear section headers like:
  "AI & Machine Learning", "Legal Tech", "Startups & SaaS", "Policy & Regulation", etc.
- For each item, write a 2-3 sentence summary that captures the key insight or news
- ALWAYS hyperlink sources using markdown link syntax: [Source Name](URL)
  For example: *Source: [TechCrunch](https://techcrunch.com/2026/...)*
  Every source attribution MUST be a clickable hyperlink when a URL is available.
  For newsletter sources without a direct URL, just use the source name in bold.
- At the top, include a "Key Trends This Week" section with 2-3 bullet points highlighting
  patterns you see across multiple sources
- Prioritize actionable insights and genuinely new developments over hype
- If multiple sources cover the same story, consolidate into one entry and list all sources
  as hyperlinks: *Sources: [TechCrunch](url1), [Ars Technica](url2)*
- Keep the total digest scannable — aim for quality over quantity
- Use markdown formatting (headers, bullets, bold for emphasis)
- Skip promotional content, sponsor messages, and job listings
"""


def summarize(newsletters, rss_articles, model, max_tokens=4096):
    """Summarize newsletters and RSS articles into a digest using Claude.

    Args:
        newsletters: List of email dicts (filtered newsletters).
        rss_articles: List of RSSArticle objects.
        model: Claude model ID to use.
        max_tokens: Maximum tokens for the response.

    Returns:
        Markdown string of the digest summary.
    """
    content_parts = []

    # Format newsletter content
    if newsletters:
        content_parts.append("=== NEWSLETTER EMAILS ===\n")
        for i, email in enumerate(newsletters, 1):
            text = extract_text(email)
            if not text.strip():
                continue
            content_parts.append(
                f"--- Newsletter {i} ---\n"
                f"From: {email.get('sender', 'Unknown')}\n"
                f"Subject: {email.get('subject', 'No subject')}\n"
                f"Date: {email.get('date', '')}\n\n"
                f"{text}\n"
            )

    # Format RSS articles
    if rss_articles:
        content_parts.append("\n=== RSS FEED ARTICLES ===\n")
        for article in rss_articles:
            content_parts.append(
                f"--- {article.source} ---\n"
                f"Title: {article.title}\n"
                f"URL: {article.url}\n"
                f"Date: {article.published.strftime('%Y-%m-%d')}\n"
                f"Summary: {article.summary}\n"
            )

    if not content_parts:
        return "No content found for this period."

    user_message = (
        "Here is the content to summarize into a digest:\n\n"
        + "\n".join(content_parts)
    )

    # Truncate if too long (Claude context is large but let's be reasonable)
    if len(user_message) > 80000:
        user_message = user_message[:80000] + "\n\n[Content truncated due to length]"

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text
