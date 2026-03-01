"""Fetch and filter articles from RSS feeds."""

from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser


@dataclass
class RSSArticle:
    title: str
    source: str
    url: str
    summary: str
    published: datetime


def fetch_feeds(feed_configs, lookback_days=4):
    """Fetch recent articles from all configured RSS feeds.

    Args:
        feed_configs: List of dicts with 'name' and 'url' keys from config.yaml.
        lookback_days: Only include articles published within this many days.

    Returns:
        List of RSSArticle objects sorted by publication date (newest first).
    """
    cutoff = datetime.now(timezone.utc).timestamp() - (lookback_days * 86400)
    articles = []

    for feed_config in feed_configs:
        name = feed_config["name"]
        url = feed_config["url"]
        try:
            feed_articles = _fetch_single_feed(name, url, cutoff)
            articles.extend(feed_articles)
        except Exception as e:
            print(f"  Warning: Failed to fetch {name}: {e}")

    articles.sort(key=lambda a: a.published, reverse=True)
    return articles


def _fetch_single_feed(name, url, cutoff_timestamp):
    """Fetch and filter articles from a single RSS feed."""
    feed = feedparser.parse(url)
    articles = []

    for entry in feed.entries:
        published = _parse_date(entry)
        if published is None:
            continue

        if published.timestamp() < cutoff_timestamp:
            continue

        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary
        elif hasattr(entry, "description"):
            summary = entry.description

        # Strip HTML tags from summary
        if summary:
            from bs4 import BeautifulSoup
            summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")
            # Truncate long summaries
            if len(summary) > 500:
                summary = summary[:500] + "..."

        link = entry.get("link", "")

        articles.append(RSSArticle(
            title=entry.get("title", "Untitled"),
            source=name,
            url=link,
            summary=summary,
            published=published,
        ))

    return articles


def _parse_date(entry):
    """Try to parse the publication date from an RSS entry."""
    for field in ("published", "updated", "created"):
        val = getattr(entry, field, None) or entry.get(f"{field}_parsed")
        if val is None:
            continue

        if isinstance(val, str):
            try:
                return dateparser.parse(val)
            except (ValueError, OverflowError):
                continue

    return None
