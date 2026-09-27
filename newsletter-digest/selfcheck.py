#!/usr/bin/env python3
"""Offline self-check for the newsletter pipeline (no pytest, no network).

Exercises dashboard_publisher.publish_dashboard_data against throwaway git
repositories (a bare "GitHub" remote plus clones standing in for the Mac
checkout and for other machines), plus the JSON repair, index handling,
HTML escaping and --dry-run behavior. Gmail, Anthropic and RSS are never
contacted; modules that would need them are stubbed.

Usage:
    python3 selfcheck.py          # prints PASS/FAIL per check, exits 1 on failure
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import types
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import dashboard_publisher as dp  # noqa: E402
import digest_formatter  # noqa: E402
import trend_extractor  # noqa: E402

DATA = dp.DATA_REL
CHECKS = []


def check(func):
    """Register a self-check function."""
    CHECKS.append(func)
    return func


# ---------------------------------------------------------------------------
# Git sandbox helpers
# ---------------------------------------------------------------------------


def git(cwd, *args):
    """Run git in ``cwd`` and return stripped stdout; raise on failure."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", *args], cwd=cwd, env=env,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def make_digest(digest_id, end_date):
    """Return a minimal but dashboard-shaped digest dict."""
    return {
        "meta": {
            "id": digest_id,
            "run_date": f"{end_date}T08:00:00",
            "date_range_start": end_date,
            "date_range_end": end_date,
            "newsletter_count": 1,
            "rss_article_count": 2,
            "sources_analyzed": ["Test"],
        },
        "topics": [{"name": "AI Agents", "category": "ai", "mention_count": 1}],
        "ai_economy_events": [],
        "regulatory_events": [],
        "legal_tech_signals": [],
        "source_contributions": [],
        "weekly_snapshot": {},
    }


def write_digest(repo, digest_id, end_date, update_index=True):
    """Write a digest into ``repo``'s data dir the way the pipeline does."""
    data_dir = os.path.join(repo, DATA)
    name = f"digest-{digest_id}.json"
    digest = make_digest(digest_id, end_date)
    dp.atomic_write_json(os.path.join(data_dir, name), digest)
    if update_index:
        trend_extractor._update_index(data_dir, digest["meta"], name)
    return f"{DATA}/{name}"


class Sandbox:
    """A bare remote, a seeded ``main`` and helpers to clone it."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="nd-selfcheck-")
        self.remote = os.path.join(self.root, "remote.git")
        git(self.root, "init", "--quiet", "--bare", "--initial-branch=main", self.remote)
        seed = os.path.join(self.root, "seed")
        git(self.root, "init", "--quiet", "--initial-branch=main", seed)
        self._configure(seed)
        with open(os.path.join(seed, "README.md"), "w") as f:
            f.write("repo\n")
        os.makedirs(os.path.join(seed, DATA))
        write_digest(seed, "2026-W30-wed", "2026-07-22")
        git(seed, "add", "-A")
        git(seed, "commit", "--quiet", "-m", "seed")
        git(seed, "remote", "add", "origin", self.remote)
        git(seed, "push", "--quiet", "origin", "main")
        self.mac = self.clone("mac")
        self.logs = []

    def _configure(self, repo):
        git(repo, "config", "user.name", "Self Check")
        git(repo, "config", "user.email", "selfcheck@example.invalid")
        git(repo, "config", "commit.gpgsign", "false")

    def clone(self, name):
        """Clone the remote into a new working copy and return its path."""
        path = os.path.join(self.root, name)
        git(self.root, "clone", "--quiet", self.remote, path)
        self._configure(path)
        return path

    def publish(self, repo=None, **kwargs):
        """Run the publisher against ``repo`` (default: the Mac checkout)."""
        kwargs.setdefault("retry_delay", 0)
        return dp.publish_dashboard_data(repo or self.mac, log=self.logs.append, **kwargs)

    def remote_head(self):
        """Return the remote main commit sha."""
        return git(self.remote, "rev-parse", "main")

    def remote_files(self):
        """Return the set of paths on remote main."""
        return set(git(self.remote, "ls-tree", "-r", "--name-only", "main").splitlines())

    def remote_index_ids(self):
        """Return the digest ids listed in remote main's index.json."""
        index = json.loads(git(self.remote, "show", f"main:{DATA}/index.json"))
        return [e["id"] for e in index["digests"]]

    def other_machine_push(self, digest_id, end_date, extra_file=None):
        """Simulate another machine pushing a digest (and a file) to main."""
        other = self.clone(f"other-{digest_id}")
        write_digest(other, digest_id, end_date)
        if extra_file:
            with open(os.path.join(other, extra_file), "w") as f:
                f.write("from elsewhere\n")
        git(other, "add", "-A")
        git(other, "commit", "--quiet", "-m", f"other {digest_id}")
        git(other, "push", "--quiet", "origin", "main")

    def cleanup(self):
        """Delete the sandbox."""
        shutil.rmtree(self.root, ignore_errors=True)


def with_sandbox(func):
    """Decorator: pass a fresh Sandbox and clean it up afterwards."""
    def wrapper():
        box = Sandbox()
        try:
            func(box)
        except BaseException:
            print("    publisher log:\n      " + "\n      ".join(box.logs))
            raise
        finally:
            box.cleanup()
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ---------------------------------------------------------------------------
# Publisher checks
# ---------------------------------------------------------------------------


@check
@with_sandbox
def publish_happy_path(box):
    """On main with unrelated staged + unstaged work: only data is pushed."""
    mac = box.mac
    write_digest(mac, "2026-W31-wed", "2026-07-29")
    with open(os.path.join(mac, "notes.txt"), "w") as f:
        f.write("wip\n")
    git(mac, "add", "notes.txt")
    with open(os.path.join(mac, "README.md"), "a") as f:
        f.write("local edit\n")

    assert box.publish() is True
    files = box.remote_files()
    assert f"{DATA}/digest-2026-W31-wed.json" in files
    assert "notes.txt" not in files, "staged unrelated file was pushed"
    assert git(box.remote, "show", "main:README.md") == "repo", "unstaged edit was pushed"
    assert box.remote_index_ids() == ["2026-W30-wed", "2026-W31-wed"]
    assert git(mac, "rev-parse", "HEAD") == box.remote_head(), "local main not fast-forwarded"
    assert git(mac, "diff", "--cached", "--name-only") == "notes.txt", "user's index changed"
    assert git(mac, "status", "--porcelain", "--", DATA) == "", "data left dirty"
    assert "local edit" in open(os.path.join(mac, "README.md")).read()

    head = box.remote_head()
    assert box.publish() is True
    assert box.remote_head() == head, "second publish made a new commit"
    assert any("already up to date" in line for line in box.logs)


@check
@with_sandbox
def publish_remote_ahead(box):
    """Remote gained a digest and another file: merged, never clobbered."""
    box.other_machine_push("2026-W31-fri", "2026-07-31", extra_file="elsewhere.txt")
    write_digest(box.mac, "2026-W32-wed", "2026-08-05")  # local index lacks W31-fri

    assert box.publish() is True
    files = box.remote_files()
    assert "elsewhere.txt" in files
    assert box.remote_index_ids() == ["2026-W30-wed", "2026-W31-fri", "2026-W32-wed"]
    parent = git(box.remote, "rev-parse", "main^")
    assert parent == git(box.remote, "rev-parse", "main~1")
    assert git(box.mac, "rev-parse", "HEAD") == box.remote_head()
    local_index = json.load(open(os.path.join(box.mac, DATA, "index.json")))
    assert [e["id"] for e in local_index["digests"]] == box.remote_index_ids()


@check
@with_sandbox
def publish_race_retries(box):
    """Remote moves between fetch and push: rejected, rebuilt, retried."""
    write_digest(box.mac, "2026-W32-fri", "2026-08-07")
    real_git = dp._git
    state = {"raced": False}

    def racing_git(repo_dir, *args, **kwargs):
        if args and args[0] == "push" and not state["raced"]:
            state["raced"] = True
            box.other_machine_push("2026-W32-wed", "2026-08-05")
        return real_git(repo_dir, *args, **kwargs)

    dp._git = racing_git
    try:
        assert box.publish() is True
    finally:
        dp._git = real_git
    assert state["raced"]
    assert any("attempt 1/3 failed" in line for line in box.logs), box.logs
    assert box.remote_index_ids() == ["2026-W30-wed", "2026-W32-wed", "2026-W32-fri"]


@check
@with_sandbox
def publish_from_wrong_branch(box):
    """On a feature branch: data goes to main; the branch is untouched."""
    mac = box.mac
    git(mac, "checkout", "--quiet", "-b", "feature")
    with open(os.path.join(mac, "feature.txt"), "w") as f:
        f.write("feature work\n")
    git(mac, "add", "feature.txt")
    git(mac, "commit", "--quiet", "-m", "feature work")
    feature_head = git(mac, "rev-parse", "HEAD")
    write_digest(mac, "2026-W33-wed", "2026-08-12")

    assert box.publish() is True
    assert f"{DATA}/digest-2026-W33-wed.json" in box.remote_files()
    assert "feature.txt" not in box.remote_files(), "feature branch content reached main"
    assert "feature" not in git(box.remote, "branch", "--list"), "feature branch was pushed"
    assert git(mac, "rev-parse", "HEAD") == feature_head, "feature branch moved"
    assert git(mac, "symbolic-ref", "--short", "HEAD") == "feature"
    assert any("not 'main'" in line for line in box.logs)

    head = box.remote_head()
    assert box.publish() is True
    assert box.remote_head() == head, "republished identical data"


@check
@with_sandbox
def publish_retried_after_network_failure(box):
    """Push fails (remote unreachable): logged, False; next run publishes."""
    mac = box.mac
    write_digest(mac, "2026-W34-wed", "2026-08-19")
    git(mac, "remote", "set-url", "origin", os.path.join(box.root, "missing.git"))
    assert box.publish() is False
    assert any("NOT published" in line for line in box.logs)
    assert f"{DATA}/digest-2026-W34-wed.json" not in box.remote_files()

    git(mac, "remote", "set-url", "origin", box.remote)
    assert box.publish() is True
    assert f"{DATA}/digest-2026-W34-wed.json" in box.remote_files()


@check
@with_sandbox
def publish_old_unpushed_commit(box):
    """A data commit left unpushed by an earlier run is published and cleaned."""
    mac = box.mac
    write_digest(mac, "2026-W35-wed", "2026-08-26")
    git(mac, "add", DATA)
    git(mac, "commit", "--quiet", "-m", "old-style data commit")
    box.other_machine_push("2026-W35-fri", "2026-08-28")

    assert box.publish() is True
    assert box.remote_index_ids() == ["2026-W30-wed", "2026-W35-wed", "2026-W35-fri"]
    assert git(mac, "rev-parse", "HEAD") == box.remote_head(), box.logs
    assert git(mac, "status", "--porcelain") == ""


@check
@with_sandbox
def publish_keeps_real_local_commits_local(box):
    """Rebecca's own unpushed commit on main is never pushed."""
    mac = box.mac
    with open(os.path.join(mac, "mine.txt"), "w") as f:
        f.write("mine\n")
    git(mac, "add", "mine.txt")
    git(mac, "commit", "--quiet", "-m", "my own work")
    mine = git(mac, "rev-parse", "HEAD")
    write_digest(mac, "2026-W36-wed", "2026-09-02")

    assert box.publish() is True
    assert "mine.txt" not in box.remote_files()
    assert f"{DATA}/digest-2026-W36-wed.json" in box.remote_files()
    assert git(mac, "rev-parse", "HEAD") == mine
    assert any("commits that are not on" in line for line in box.logs)


@check
@with_sandbox
def publish_skips_corrupt_digest(box):
    """A half-written digest file is never published."""
    mac = box.mac
    with open(os.path.join(mac, DATA, "digest-2026-W37-wed.json"), "w") as f:
        f.write('{"meta": {"id": "2026-W37-wed"')
    write_digest(mac, "2026-W37-fri", "2026-09-11")

    assert box.publish() is True
    files = box.remote_files()
    assert f"{DATA}/digest-2026-W37-wed.json" not in files
    assert f"{DATA}/digest-2026-W37-fri.json" in files
    assert any("skipping" in line for line in box.logs)


@check
@with_sandbox
def publish_repairs_index(box):
    """A digest the local index forgot (crash between writes) is still indexed."""
    write_digest(box.mac, "2026-W38-wed", "2026-09-16", update_index=False)
    assert box.publish() is True
    assert box.remote_index_ids() == ["2026-W30-wed", "2026-W38-wed"]


@check
def publish_outside_repo():
    """Not a git repo: returns False and logs, never raises."""
    logs = []
    tmp = tempfile.mkdtemp(prefix="nd-selfcheck-norepo-")
    try:
        assert dp.publish_dashboard_data(tmp, log=logs.append, retry_delay=0) is False
        assert any("ERROR" in line for line in logs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Extraction, index and formatting checks
# ---------------------------------------------------------------------------


@check
def extraction_json_parsing():
    """Fenced, prose-wrapped and truncated model output is recovered."""
    parse = trend_extractor.parse_extraction_response
    assert parse('```json\n{"topics": []}\n```') == {"topics": []}
    assert parse('Here you go:\n{"topics": [1]} trailing') == {"topics": [1]}
    assert parse("```") is None
    assert parse("no json here") is None
    truncated = '{"topics": [{"name": "A"}, {"name": "B", "headl'
    assert parse(truncated) == {"topics": [{"name": "A"}, {"name": "B"}]}
    truncated = '```json\n{"topics": [{"name": "A \\" } ["}], "ai_economy_events": [{"type'
    assert parse(truncated) == {"topics": [{"name": 'A " } ['}]}


@check
def extraction_normalization():
    """Malformed sections are coerced so the dashboard never breaks."""
    norm = trend_extractor.normalize_extraction({
        "meta": {"id": "evil"},
        "topics": [{"name": "A"}, "junk", {"noname": 1}],
        "ai_economy_events": "oops",
        "weekly_snapshot": [],
    })
    assert "meta" not in norm
    assert norm["topics"] == [{"name": "A"}]
    assert norm["ai_economy_events"] == [] and norm["regulatory_events"] == []
    assert norm["weekly_snapshot"] == {}


@check
def index_update_recovers_from_corruption():
    """A corrupt local index.json is rebuilt from the digest files."""
    tmp = tempfile.mkdtemp(prefix="nd-selfcheck-index-")
    try:
        for digest_id, day in (("2026-W30-wed", "2026-07-22"), ("2026-W31-wed", "2026-07-29")):
            dp.atomic_write_json(os.path.join(tmp, f"digest-{digest_id}.json"),
                                 make_digest(digest_id, day))
        with open(os.path.join(tmp, "index.json"), "w") as f:
            f.write('{"digests": [')
        meta = make_digest("2026-W32-wed", "2026-08-05")["meta"]
        trend_extractor._update_index(tmp, meta, "digest-2026-W32-wed.json")
        index = json.load(open(os.path.join(tmp, "index.json")))
        assert [e["id"] for e in index["digests"]] == [
            "2026-W30-wed", "2026-W31-wed", "2026-W32-wed"]
        assert not [n for n in os.listdir(tmp) if n.startswith(".tmp-")], "temp file left"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check
def email_html_is_escaped():
    """Model output cannot inject markup or non-http(s) links into the email."""
    fmt = digest_formatter._inline_format
    out = fmt('<img src=x onerror=alert(1)> [ok](https://a.com/?x=1&y="2") '
              '[bad](javascript:alert(1)) **b** *i*')
    assert "<img" not in out and "&lt;img" in out
    assert '<a href="https://a.com/?x=1&amp;y=&quot;2&quot;">ok</a>' in out
    assert "javascript:" not in out.split("bad")[0] and 'href="javascript' not in out
    assert "<strong>b</strong>" in out and "<em>i</em>" in out
    html = digest_formatter.format_digest_html("## <b>Head</b>\n- [x](data:text/html,hi)",
                                               "Jan 1", "Jan 3")
    assert "&lt;b&gt;Head" in html and 'href="data:' not in html


@check
def dry_run_has_no_side_effects():
    """--dry-run never extracts trends, writes data or publishes."""
    calls = []

    def stub(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        sys.modules[name] = module

    article = types.SimpleNamespace(source="Feed", title="T", url="https://e.com",
                                    summary="s", published=datetime.now())
    saved = {n: sys.modules.get(n) for n in
             ("gmail_client", "rss_fetcher", "summarizer", "trend_extractor", "main")}
    stub("gmail_client", fetch_emails=lambda **k: [],
         send_email=lambda *a: calls.append("send_email"))
    stub("rss_fetcher", fetch_feeds=lambda **k: [article])
    stub("summarizer", summarize=lambda **k: "# Digest")
    stub("trend_extractor", extract_trends=lambda **k: calls.append("extract_trends"))
    sys.modules.pop("main", None)
    try:
        import main
        main.publish_dashboard_data = lambda *a, **k: calls.append("publish") or True
        for argv in (["--dry-run"], ["--dry-run", "--trends-only"],
                     ["--dry-run", "--backfill", "2026-04-15"]):
            assert main.main(argv) == 0
        assert calls == [], f"dry run had side effects: {calls}"
        assert main.main(["--skip-trends"]) == 0
        assert calls == ["send_email"], calls
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def main():
    """Run every registered check and return an exit code."""
    failures = 0
    for func in CHECKS:
        try:
            func()
            print(f"PASS  {func.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL  {func.__name__}: {func.__doc__}")
            traceback.print_exc()
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
