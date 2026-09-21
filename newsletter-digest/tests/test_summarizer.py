"""Tests for response handling in the summarizer."""

import unittest
from types import SimpleNamespace

from summarizer import extract_response_text


def _response(blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


class ExtractResponseTextTests(unittest.TestCase):
    """Text blocks are joined; empty responses fail loudly."""

    def test_joins_text_blocks_and_skips_others(self):
        resp = _response([
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text="Hello "),
            SimpleNamespace(type="text", text="world"),
        ])
        self.assertEqual(extract_response_text(resp), "Hello world")

    def test_refusal_raises(self):
        with self.assertRaises(RuntimeError):
            extract_response_text(_response([], stop_reason="refusal"))

    def test_truncation_still_returns_text(self):
        resp = _response([SimpleNamespace(type="text", text="partial")], "max_tokens")
        self.assertEqual(extract_response_text(resp), "partial")


if __name__ == "__main__":
    unittest.main()
