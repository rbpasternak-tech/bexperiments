"""Tests for the inbox sweep's pickiness rules in vault_jobs.py.

Run: .venv/bin/python -m unittest test_sweep_rules
"""

import unittest

import vault_jobs as vj


class FakeVault:
    def __init__(self, urls=()):
        self.urls = set(urls)

    def queue_urls(self):
        return set(self.urls)


ME = "Rebecca Pasternak <rbpasternak@gmail.com>"


def item(title, url, source):
    return f"- [ ] **{title}** — {url} _(saved 2026-10-03, {source})_ (x)"


class FilterTests(unittest.TestCase):
    def test_excluded_senders_and_digests(self):
        msgs = [
            {"from": "Patch <noreply@patch.com>", "subject": "Cheshire news", "urls": []},
            {"from": "Nextdoor <no-reply@rs.email.nextdoor.com>", "subject": "x", "urls": []},
            {"from": "NYT Cooking <nytdirect@nytimes.com>", "subject": "pumpkin", "urls": []},
            {"from": "nytdirect@nytimes.com", "subject": "Solve a Friday crossword on Easy Mode", "urls": []},
            {"from": "nytdirect@nytimes.com", "subject": "kebabs",
             "snippet": "View in browser|nytimes.com Ad Ad Cooking October 1", "urls": []},
            {"from": "cooking-recommendations@nytimes.com", "subject": "Hummus and More", "urls": []},
            {"from": ME, "to": ME, "subject": "Daily AI Competitive Intelligence - Peer Firms", "urls": []},
            {"from": ME, "to": ME, "subject": "Your Tech & Legal Tech Digest — Sep 30, 2026", "urls": []},
        ]
        kept, hidden = vj._filter_sweep_messages(msgs)
        self.assertEqual(kept, [])
        self.assertEqual(sum(hidden.values()), len(msgs))

    def test_keeps_news_and_self_sends(self):
        msgs = [
            {"from": "nytdirect@nytimes.com", "subject": "The Morning: AI and law firms",
             "snippet": "View in browser|nytimes.com Ad The Morning", "urls": ["https://www.nytimes.com/2026/10/02/tech/ai.html"]},
            {"from": "The Columbus Dispatch <news@dispatch.com>", "subject": "x", "urls": []},
            {"from": ME, "to": ME, "subject": "https://example.com/a", "urls": ["https://example.com/a"]},
        ]
        kept, hidden = vj._filter_sweep_messages(msgs)
        self.assertEqual(len(kept), 3)
        self.assertEqual(hidden, {})
        self.assertTrue(kept[2]["self_send"])
        self.assertFalse(kept[0]["self_send"])


class GateTests(unittest.TestCase):
    def ctx(self, urls=(), cap=5):
        return {"vault": FakeVault(urls), "sweep_cap": cap, "sweep_added": 0}

    def test_self_sends_always_kept_and_first(self):
        ctx = self.ctx(cap=2)
        items = [item(f"u{i}", f"https://news.example/{i}", "unread") for i in range(3)]
        items += [item(f"s{i}", f"https://self.example/{i}", "self-send") for i in range(3)]
        kept, refused = vj._gate_sweep_items(items, ctx)
        self.assertEqual([k for k in kept if "self-send" in k], items[3:])
        self.assertEqual(len(kept), 3)
        self.assertEqual(len(refused), 3)

    def test_cap_and_gmail_only_links(self):
        ctx = self.ctx(cap=5)
        items = [item("gm", "https://mail.google.com/mail/u/0/#inbox/abc", "unread")]
        items += [item(f"u{i}", f"https://news.example/{i}", "unread") for i in range(7)]
        kept, refused = vj._gate_sweep_items(items, ctx)
        self.assertEqual(len(kept), 5)
        self.assertEqual(len(refused), 3)
        self.assertIn("Gmail-only", refused[0][0])
        # A later call in the same run is still capped.
        kept2, refused2 = vj._gate_sweep_items([item("late", "https://news.example/late", "unread")], ctx)
        self.assertEqual(kept2, [])

    def test_self_send_gmail_permalink_allowed(self):
        kept, refused = vj._gate_sweep_items(
            [item("s", "https://mail.google.com/mail/u/0/#inbox/abc", "self-send")], self.ctx())
        self.assertEqual(len(kept), 1)

    def test_duplicates_do_not_use_cap(self):
        ctx = self.ctx(urls={"https://dup.example/1"}, cap=1)
        items = [item("d", "https://dup.example/1", "unread"), item("n", "https://news.example/1", "unread")]
        kept, refused = vj._gate_sweep_items(items, ctx)
        self.assertEqual(len(kept), 2)
        self.assertEqual(refused, [])


class FlagCapTests(unittest.TestCase):
    def test_trims_to_counts_plus_five(self):
        body = "Added 3 (2 self-send, 1 unread); 40 dropped.\n" + "\n".join(f"- flag {i}" for i in range(9))
        out = vj._cap_sweep_flags(body).splitlines()
        self.assertEqual(len(out), 7)
        self.assertIn("+4", out[-1])

    def test_short_body_unchanged(self):
        body = "Counts.\n- one\n- two"
        self.assertEqual(vj._cap_sweep_flags(body), body)


if __name__ == "__main__":
    unittest.main()
