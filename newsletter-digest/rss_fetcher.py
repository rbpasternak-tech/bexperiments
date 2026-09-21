"""Fetch and filter articles from RSS feeds."""

import calendar
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup
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
            summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")
            summary = " ".join(summary.split())
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
    """Try to parse the publication date from an RSS entry.

    Returns a timezone-aware UTC datetime, or None if no usable date is found.
    Feeds mix naive and offset-bearing timestamps, so everything is normalized
    to UTC to keep cutoff comparisons and sorting consistent.
    """
    for field in ("published", "updated", "created"):
        parsed = entry.get(f"{field}_parsed")
        if isinstance(parsed, time.struct_time):
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)

        raw = entry.get(field)
        if isinstance(raw, str) and raw.strip():
            try:
                return _to_utc(dateparser.parse(raw))
            except (ValueError, OverflowError, TypeError):
                continue

    return None


def _to_utc(dt):
    """Normalize a datetime to timezone-aware UTC (naive values are assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
