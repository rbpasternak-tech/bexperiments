"""Fetch and filter articles from RSS feeds."""

import calendar
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# feedparser has no timeout of its own; without one a single stalled feed
# can hang the unattended launchd run forever.
FEED_TIMEOUT_SECONDS = 30
MAX_SUMMARY_CHARS = 500


@dataclass
class RSSArticle:
    """One article from an RSS or Atom feed."""

    title: str
    source: str
    url: str
    summary: str
    published: datetime


def fetch_feeds(feed_configs, lookback_days=4, end_date=None):
    """Fetch recent articles from all configured RSS feeds.

    Args:
        feed_configs: List of dicts with 'name' and 'url' keys from config.yaml.
        lookback_days: Only include articles published within this many days
            before ``end_date``.
        end_date: datetime closing the window (defaults to now). Articles
            published after the end of that day are excluded, which keeps
            ``--backfill`` windows from picking up today's articles.

    Returns:
        List of RSSArticle objects sorted by publication date (newest first),
        de-duplicated by URL.
    """
    if end_date is None:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=lookback_days)
        # Small allowance for feeds with skewed or mislabelled timezones.
        window_end = now + timedelta(days=1)
    else:
        if end_date.tzinfo is None:
            end_date = end_date.astimezone()  # interpret naive as local time
        window_end = end_date.replace(hour=23, minute=59, second=59)
        window_start = window_end - timedelta(days=lookback_days)

    articles = []
    seen_urls = set()
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(FEED_TIMEOUT_SECONDS)
    try:
        for feed_config in feed_configs:
            name = feed_config.get("name") or feed_config.get("url", "Unknown feed")
            url = feed_config.get("url")
            if not url:
                print(f"  Warning: feed {name!r} has no url; skipping")
                continue
            try:
                feed_articles = _fetch_single_feed(name, url, window_start, window_end)
            except Exception as e:
                print(f"  Warning: Failed to fetch {name}: {e}")
                continue
            for article in feed_articles:
                if article.url and article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                articles.append(article)
    finally:
        socket.setdefaulttimeout(old_timeout)

    articles.sort(key=lambda a: a.published, reverse=True)
    return articles


def _fetch_single_feed(name, url, window_start, window_end):
    """Fetch and filter articles from a single RSS feed.

    Args:
        name: Display name of the feed.
        url: Feed URL.
        window_start: Earliest aware datetime to include.
        window_end: Latest aware datetime to include.

    Returns:
        List of RSSArticle objects within the window.
    """
    feed = feedparser.parse(url)
    status = getattr(feed, "status", None)
    if not feed.entries:
        problem = getattr(feed, "bozo_exception", None) or (
            f"HTTP {status}" if status else "no entries")
        print(f"  Warning: {name} returned no entries ({problem})")
        return []

    articles = []
    for entry in feed.entries:
        published = _parse_date(entry)
        if published is None or not (window_start <= published <= window_end):
            continue

        summary = entry.get("summary") or entry.get("description") or ""
        if summary:
            summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")
            summary = " ".join(summary.split())
            if len(summary) > MAX_SUMMARY_CHARS:
                summary = summary[:MAX_SUMMARY_CHARS] + "..."

        articles.append(RSSArticle(
            title=(entry.get("title") or "Untitled").strip(),
            source=name,
            url=entry.get("link", ""),
            summary=summary,
            published=published,
        ))

    return articles


def _parse_date(entry):
    """Return an aware publication datetime for an RSS entry, or None.

    Tries the raw date strings first, then feedparser's pre-parsed UTC
    ``*_parsed`` struct_time values.
    """
    for field in ("published", "updated", "created"):
        val = entry.get(field)
        if isinstance(val, str) and val.strip():
            try:
                parsed = dateparser.parse(val)
            except (ValueError, OverflowError, TypeError):
                parsed = None
            if parsed is not None:
                # Assume UTC for feeds that omit an offset, so naive and aware
                # dates can be compared when sorting.
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed

        struct = entry.get(f"{field}_parsed")
        if struct:
            try:
                return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue

    return None
