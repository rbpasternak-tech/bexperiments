"""Tests for trend extraction helpers that need no API access."""

import json
import os
import tempfile
import unittest
from datetime import datetime

from trend_extractor import _make_digest_id, _repair_truncated_json, _update_index


class RepairJsonTests(unittest.TestCase):
    """Recovery of truncated JSON responses."""

    def test_valid_prefix_recovered(self):
        raw = '{"topics": [{"name": "AI"}], "events": [{"entity": "X"'
        self.assertEqual(_repair_truncated_json(raw), {"topics": [{"name": "AI"}]})

    def test_truncated_inside_string_drops_partial_item(self):
        raw = '{"topics": [{"name": "A"}, {"name": "B}"}], "events": [{"entity": "X'
        self.assertEqual(
            _repair_truncated_json(raw),
            {"topics": [{"name": "A"}, {"name": "B}"}]},
        )

    def test_complete_json_with_trailing_junk(self):
        self.assertEqual(_repair_truncated_json('{"a": [1]} trailing'), {"a": [1]})

    def test_hopeless_input(self):
        self.assertIsNone(_repair_truncated_json("garbage"))


class DigestIdTests(unittest.TestCase):
    """Digest IDs follow YYYY-Www-day."""

    def test_format(self):
        self.assertEqual(_make_digest_id(datetime(2026, 3, 6)), "2026-W10-fri")
        self.assertEqual(_make_digest_id(datetime(2026, 1, 1)), "2026-W01-thu")


class UpdateIndexTests(unittest.TestCase):
    """index.json is created, deduplicated, and sorted."""

    def _meta(self, digest_id, end):
        return {
            "id": digest_id,
            "date_range_start": end,
            "date_range_end": end,
            "newsletter_count": 1,
            "rss_article_count": 2,
        }

    def test_create_replace_and_sort(self):
        with tempfile.TemporaryDirectory() as tmp:
            _update_index(tmp, self._meta("b", "2026-02-01"), "b.json")
            _update_index(tmp, self._meta("a", "2026-01-01"), "a.json")
            _update_index(tmp, self._meta("b", "2026-02-02"), "b2.json")

            with open(os.path.join(tmp, "index.json")) as f:
                index = json.load(f)

        ids = [d["id"] for d in index["digests"]]
        self.assertEqual(ids, ["a", "b"])
        self.assertEqual(index["digests"][1]["file"], "b2.json")
        self.assertIsNotNone(index["last_updated"])


if __name__ == "__main__":
    unittest.main()
