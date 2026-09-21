"""Tests for RSS fetching and date normalization."""

import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import rss_fetcher
from rss_fetcher import _parse_date, fetch_feeds


class FakeEntry(dict):
    """Mimics feedparser's attribute-and-key entry access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class ParseDateTests(unittest.TestCase):
    """Every accepted date shape normalizes to aware UTC."""

    def test_struct_time_is_used(self):
        st = time.gmtime(1_700_000_000)
        dt = _parse_date(FakeEntry(published_parsed=st))
        self.assertEqual(dt, datetime.fromtimestamp(1_700_000_000, tz=timezone.utc))

    def test_string_with_offset(self):
        dt = _parse_date(FakeEntry(published="Mon, 01 Jan 2026 10:00:00 +0200"))
        self.assertEqual(dt, datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))

    def test_naive_string_assumed_utc(self):
        dt = _parse_date(FakeEntry(updated="2026-01-01T10:00:00"))
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt.hour, 10)

    def test_unparseable_then_fallback_field(self):
        dt = _parse_date(FakeEntry(published="not a date", updated="2026-02-02"))
        self.assertEqual(dt.date(), datetime(2026, 2, 2).date())

    def test_no_date(self):
        self.assertIsNone(_parse_date(FakeEntry(title="x")))


class FetchFeedsTests(unittest.TestCase):
    """Feed filtering, HTML stripping, and mixed-timezone sorting."""

    def _feed(self, entries):
        return mock.Mock(entries=entries)

    def test_mixed_timezones_sort_and_cutoff(self):
        now = datetime.now(timezone.utc)
        recent_naive = (now - timedelta(hours=1)).replace(tzinfo=None).isoformat()
        recent_aware = (now - timedelta(hours=5)).isoformat()
        old = (now - timedelta(days=10)).isoformat()
        entries = [
            FakeEntry(title="aware", link="a", published=recent_aware,
                      summary="<p>Hi <b>there</b></p>"),
            FakeEntry(title="naive", link="b", published=recent_naive),
            FakeEntry(title="old", link="c", published=old),
            FakeEntry(title="undated", link="d"),
        ]
        with mock.patch.object(rss_fetcher.feedparser, "parse",
                               return_value=self._feed(entries)):
            articles = fetch_feeds([{"name": "Feed", "url": "u"}], lookback_days=4)

        self.assertEqual([a.title for a in articles], ["naive", "aware"])
        self.assertEqual(articles[1].summary, "Hi there")
        self.assertEqual(articles[0].source, "Feed")

    def test_feed_failure_is_isolated(self):
        good = FakeEntry(title="ok", link="x",
                         published=datetime.now(timezone.utc).isoformat())
        with mock.patch.object(
            rss_fetcher.feedparser, "parse",
            side_effect=[RuntimeError("boom"), self._feed([good])],
        ):
            articles = fetch_feeds(
                [{"name": "Bad", "url": "b"}, {"name": "Good", "url": "g"}],
                lookback_days=1,
            )
        self.assertEqual([a.title for a in articles], ["ok"])

    def test_long_summary_truncated(self):
        entry = FakeEntry(title="t", link="l", summary="z" * 600,
                          published=datetime.now(timezone.utc).isoformat())
        with mock.patch.object(rss_fetcher.feedparser, "parse",
                               return_value=self._feed([entry])):
            [article] = fetch_feeds([{"name": "F", "url": "u"}])
        self.assertEqual(len(article.summary), 503)
        self.assertTrue(article.summary.endswith("..."))


if __name__ == "__main__":
    unittest.main()
