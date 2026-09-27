#!/usr/bin/env python3
"""Publish trends-dashboard data to GitHub ``main`` safely and unattended.

GitHub Pages serves the ``main`` branch, so dashboard data only goes live
once it lands on ``origin/main``. The scheduled job runs unattended on a Mac
where the checkout may be on a feature branch, have unrelated uncommitted or
staged work, or be behind the remote. This module therefore never commits on
the checked-out branch and never touches the working tree or the user's
index while building the commit:

1. ``git fetch`` the remote ``main``.
2. Collect pending data files: JSON files under ``trends-dashboard/data/``
   that are new or modified in the working tree, or were committed locally
   but never reached ``origin/main`` (for example a commit whose push
   failed on an earlier run).
3. Build a new tree from ``origin/main`` plus those files in a temporary
   index, merge ``index.json`` entry by entry (rebuilding entries from each
   digest's own ``meta`` so a stale or half-written local index cannot drop
   digests), and create a single commit whose parent is ``origin/main``.
4. Push that commit to ``refs/heads/main`` (never forced). If the remote
   moved in the meantime the push is rejected as non-fast-forward, so the
   whole thing is rebuilt on the new ``origin/main`` and retried.
5. If ``main`` is checked out and has no local-only commits, fast-forward
   it so the local checkout matches what was published.

Because pending files are recomputed from disk every run, anything that
failed to publish (no network, credentials unavailable) is retried
automatically on the next run. Nothing but ``trends-dashboard/data/*.json``
is ever pushed.

Run ``python dashboard_publisher.py`` to publish pending data by hand.
"""

import fnmatch
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

DATA_REL = "trends-dashboard/data"
INDEX_NAME = "index.json"
DIGEST_PATTERN = "digest-*.json"
DEFAULT_REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Never let git block waiting for a password or a GUI credential prompt
# under launchd; fail fast instead and retry on the next run.
_GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "never",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
}


class GitError(RuntimeError):
    """A git command failed or timed out."""


# ---------------------------------------------------------------------------
# JSON / index helpers shared with trend_extractor.py
# ---------------------------------------------------------------------------


def atomic_write_json(path, obj):
    """Write ``obj`` as JSON to ``path`` atomically.

    The data is written to a temporary file in the same directory, flushed to
    disk, then renamed over the target, so a crash or full disk never leaves
    a truncated file behind.
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_json_file(path):
    """Return parsed JSON from ``path``, or ``None`` if missing or invalid."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def index_entry_from_meta(meta, filename):
    """Build an ``index.json`` digest entry from a digest file's ``meta``."""
    return {
        "id": meta["id"],
        "run_date": meta.get("date_range_end") or str(meta.get("run_date", ""))[:10],
        "date_range_start": meta.get("date_range_start"),
        "date_range_end": meta.get("date_range_end"),
        "file": filename,
        "newsletter_count": meta.get("newsletter_count", 0),
        "rss_article_count": meta.get("rss_article_count", 0),
    }


def is_valid_digest(obj):
    """Return True if ``obj`` looks like a digest with a usable ``meta.id``."""
    return (
        isinstance(obj, dict)
        and isinstance(obj.get("meta"), dict)
        and isinstance(obj["meta"].get("id"), str)
        and bool(obj["meta"]["id"])
    )


def sort_index_entries(entries):
    """Sort index entries oldest first by run date, then id."""
    return sorted(entries, key=lambda e: (str(e.get("run_date") or ""), str(e.get("id") or "")))


def rebuild_index_from_dir(data_dir):
    """Rebuild index entries from every valid digest file in ``data_dir``."""
    entries = []
    for name in sorted(os.listdir(data_dir)):
        if not fnmatch.fnmatch(name, DIGEST_PATTERN):
            continue
        digest = read_json_file(os.path.join(data_dir, name))
        if is_valid_digest(digest):
            entries.append(index_entry_from_meta(digest["meta"], name))
    return sort_index_entries(entries)


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------


def _git(repo_dir, *args, env=None, input_data=None, timeout=120, check=True):
    """Run a git command and return its stdout as text.

    Raises GitError on a non-zero exit (when ``check``) or a timeout.
    """
    full_env = dict(os.environ)
    full_env.update(_GIT_ENV)
    if env:
        full_env.update(env)
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_dir,
            env=full_env,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git {args[0]} timed out after {timeout}s") from e
    except OSError as e:
        raise GitError(f"could not run git: {e}") from e
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitError(f"git {' '.join(args[:2])} failed: {detail}")
    return result.stdout


def _git_ok(repo_dir, *args, timeout=120):
    """Return True if the git command exits 0."""
    try:
        _git(repo_dir, *args, timeout=timeout)
        return True
    except GitError:
        return False


def _pending_paths(repo_dir, base, data_rel):
    """Return repo-relative data JSON paths that may need publishing.

    Includes files that are untracked or modified in the working tree and
    files changed on the local side since the merge base with ``base``
    (local commits that never reached the remote).
    """
    paths = set()

    out = _git(repo_dir, "status", "--porcelain=v1", "-z", "--untracked-files=all",
               "--", data_rel)
    tokens = out.split("\0")
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # skip the rename/copy source path
        if "D" in status:
            continue
        paths.add(path)

    if _git_ok(repo_dir, "merge-base", base, "HEAD"):
        out = _git(repo_dir, "diff", "--name-only", "-z", "--diff-filter=AM",
                   f"{base}...HEAD", "--", data_rel)
        paths.update(p for p in out.split("\0") if p)

    def wanted(path):
        name = os.path.basename(path)
        return (
            os.path.dirname(path) == data_rel
            and (name == INDEX_NAME or fnmatch.fnmatch(name, DIGEST_PATTERN))
            and os.path.isfile(os.path.join(repo_dir, path))
        )

    return sorted(p for p in paths if wanted(p))


def _tree_files(repo_dir, rev, data_rel):
    """Return {filename: blob_sha} for files directly under ``data_rel`` at ``rev``."""
    out = _git(repo_dir, "ls-tree", "-z", rev, f"{data_rel}/")
    files = {}
    for line in out.split("\0"):
        if not line:
            continue
        info, path = line.split("\t", 1)
        _mode, obj_type, sha = info.split()
        if obj_type == "blob":
            files[os.path.basename(path)] = sha
    return files


def _read_blob_json(repo_dir, sha):
    """Return parsed JSON from a blob, or None if it is not valid JSON."""
    try:
        return json.loads(_git(repo_dir, "cat-file", "blob", sha))
    except (GitError, ValueError):
        return None


def _commit_env(repo_dir):
    """Return an author/committer env fallback if git has no identity set."""
    name = _git(repo_dir, "config", "user.name", check=False).strip()
    email = _git(repo_dir, "config", "user.email", check=False).strip()
    if name and email:
        return {}
    fallback_name = name or "newsletter-digest"
    fallback_email = email or "newsletter-digest@localhost"
    return {
        "GIT_AUTHOR_NAME": fallback_name,
        "GIT_AUTHOR_EMAIL": fallback_email,
        "GIT_COMMITTER_NAME": fallback_name,
        "GIT_COMMITTER_EMAIL": fallback_email,
    }


def _load_pending_digests(repo_dir, pending, log):
    """Return {filename: digest_dict} for the valid pending digest files.

    Invalid or half-written files are skipped with a warning so they are
    never published; ``index.json`` is merged separately, never copied.
    """
    digests = {}
    for path in pending:
        name = os.path.basename(path)
        if name == INDEX_NAME:
            continue
        obj = read_json_file(os.path.join(repo_dir, path))
        if not is_valid_digest(obj):
            log(f"  Warning: skipping {path}: not valid digest JSON "
                "(partial write or corrupt file?).")
            continue
        digests[name] = obj
    return digests


def _merge_index(repo_dir, base_files, digests, log):
    """Merge the remote index.json with entries for the pending digests.

    Entries are rebuilt from each digest's own ``meta``, and digests on the
    remote that the index does not reference are added back, so a stale or
    corrupt index can never hide data.

    Returns:
        (index_dict, changed) where ``changed`` is True if the entry list
        differs from the remote's.
    """
    remote_index = None
    if INDEX_NAME in base_files:
        remote_index = _read_blob_json(repo_dir, base_files[INDEX_NAME])
        if not isinstance(remote_index, dict) or not isinstance(remote_index.get("digests"), list):
            log("  Warning: origin's index.json is corrupt; rebuilding it from digest files.")
            remote_index = None
    index = dict(remote_index) if remote_index else {"last_updated": None, "digests": []}
    entries = {e["id"]: e for e in index["digests"] if isinstance(e, dict) and e.get("id")}
    referenced = {e.get("file") for e in entries.values()}

    for name, obj in digests.items():
        entries[obj["meta"]["id"]] = index_entry_from_meta(obj["meta"], name)
        referenced.add(name)

    for name, sha in base_files.items():
        if fnmatch.fnmatch(name, DIGEST_PATTERN) and name not in referenced:
            obj = _read_blob_json(repo_dir, sha)
            if is_valid_digest(obj):
                entries.setdefault(obj["meta"]["id"], index_entry_from_meta(obj["meta"], name))

    new_entries = sort_index_entries(entries.values())
    changed = remote_index is None or new_entries != remote_index["digests"]
    index["digests"] = new_entries
    return index, changed


def _write_tree(repo_dir, base, files):
    """Return the tree sha of ``base`` with ``files`` ({path: blob_sha}) applied.

    Uses a throwaway index file so the user's index is never touched.
    """
    tmp_dir = tempfile.mkdtemp(prefix="dashboard-publish-")
    env = {"GIT_INDEX_FILE": os.path.join(tmp_dir, "index")}
    try:
        _git(repo_dir, "read-tree", base, env=env)
        for path, sha in files.items():
            _git(repo_dir, "update-index", "--add", "--cacheinfo",
                 f"100644,{sha},{path}", env=env)
        return _git(repo_dir, "write-tree", env=env).strip()
    finally:
        try:
            os.unlink(env["GIT_INDEX_FILE"])
        except OSError:
            pass
        os.rmdir(tmp_dir)


def _build_commit(repo_dir, base, data_rel, pending, log):
    """Build a commit on ``base`` containing the pending data files.

    Returns:
        (commit_sha or None if nothing changed, merged_index_dict,
        list of published repo-relative paths).
    """
    base_files = _tree_files(repo_dir, base, data_rel)
    digests = _load_pending_digests(repo_dir, pending, log)
    index, index_changed = _merge_index(repo_dir, base_files, digests, log)

    files = {}
    for name in sorted(digests):
        sha = _git(repo_dir, "hash-object", "-w", "--", f"{data_rel}/{name}").strip()
        if base_files.get(name) != sha:
            files[f"{data_rel}/{name}"] = sha

    if not files and not index_changed:
        return None, index, []

    # Bump last_updated so browsers drop their cached copy of the data.
    index["last_updated"] = datetime.now().isoformat()
    text = json.dumps(index, indent=2) + "\n"
    files[f"{data_rel}/{INDEX_NAME}"] = _git(
        repo_dir, "hash-object", "-w", "--stdin", input_data=text).strip()

    tree = _write_tree(repo_dir, base, files)
    digest_count = len(files) - 1
    message = (f"Update trends dashboard data — {datetime.now():%Y-%m-%d}"
               f" ({digest_count} digest{'s' if digest_count != 1 else ''})\n\n"
               "Published automatically by newsletter-digest/dashboard_publisher.py.")
    commit = _git(repo_dir, "commit-tree", tree, "-p", base, "-m", message,
                  env=_commit_env(repo_dir)).strip()
    return commit, index, sorted(files)


def _local_commits_already_published(repo_dir, tracking, data_rel):
    """Return True if every local-only commit is dashboard data now on the remote.

    That is: the commits on HEAD that are not on ``tracking`` only touch
    files under ``data_rel``, each digest file matches the remote copy, and
    the remote index.json lists every digest the local one does.
    """
    changed = [p for p in _git(repo_dir, "diff", "--name-only", "-z",
                               f"{tracking}...HEAD").split("\0") if p]
    if not changed or any(os.path.dirname(p) != data_rel for p in changed):
        return False
    for path in changed:
        local = _git(repo_dir, "rev-parse", "--verify", "--quiet", f"HEAD:{path}",
                     check=False).strip()
        remote = _git(repo_dir, "rev-parse", "--verify", "--quiet", f"{tracking}:{path}",
                      check=False).strip()
        if os.path.basename(path) != INDEX_NAME:
            if local != remote:
                return False
            continue
        local_index = _read_blob_json(repo_dir, local) if local else None
        remote_index = _read_blob_json(repo_dir, remote) if remote else None
        try:
            local_ids = {e["id"] for e in local_index["digests"]}
            remote_ids = {e["id"] for e in remote_index["digests"]}
        except (TypeError, KeyError):
            return False
        if not local_ids <= remote_ids:
            return False
    return True


def _sync_local_checkout(repo_dir, remote, branch, data_rel, index, log):
    """Bring the local checkout in line with what was just published.

    If ``branch`` is checked out and has no local-only commits, writes the
    merged index.json into the working tree and fast-forwards the branch.
    Other branches are left completely alone.
    Never discards or overwrites the user's own changes.
    """
    tracking = f"refs/remotes/{remote}/{branch}"
    current = _git(repo_dir, "symbolic-ref", "--quiet", "--short", "HEAD",
                   check=False).strip()
    if current != branch:
        where = f"branch '{current}'" if current else "a detached HEAD"
        log(f"  NOTE: the repo is on {where}, not '{branch}'. The data was "
            f"published straight to {remote}/{branch}; your branch was not "
            f"touched. Check out '{branch}' and pull when convenient.")
        return

    if not _git_ok(repo_dir, "merge-base", "--is-ancestor", "HEAD", tracking):
        if _local_commits_already_published(repo_dir, tracking, data_rel):
            # Only data commits whose content is now on the remote (e.g. an
            # earlier run committed but failed to push): drop them locally.
            # --keep refuses rather than overwrite uncommitted changes.
            try:
                _git(repo_dir, "reset", "--keep", "--quiet", tracking)
                log(f"  Local '{branch}' had unpushed data-only commits that are now "
                    f"published; reset it to {remote}/{branch}.")
                return
            except GitError as e:
                log(f"  NOTE: could not reset local '{branch}' to {remote}/{branch} ({e}).")
                return
        log(f"  NOTE: local '{branch}' has commits that are not on {remote}/{branch}; "
            "not fast-forwarding it. Pull (and push your own work) when convenient.")
        return

    # Keep the local index.json identical to the published one (the merge
    # may have added entries from the remote).
    index_path = os.path.join(repo_dir, data_rel, INDEX_NAME)
    if read_json_file(index_path) != index:
        atomic_write_json(index_path, index)

    # Paths whose working-tree copy already equals the published version are
    # staged first, so the fast-forward does not trip over them.
    changed = _git(repo_dir, "diff", "--name-only", "-z", "HEAD", tracking,
                   "--", data_rel).split("\0")
    to_stage = []
    for path in filter(None, changed):
        full = os.path.join(repo_dir, path)
        if not os.path.isfile(full):
            continue
        remote_sha = _git(repo_dir, "rev-parse", "--verify", "--quiet",
                          f"{tracking}:{path}", check=False).strip()
        local_sha = _git(repo_dir, "hash-object", "--", path).strip()
        if remote_sha and remote_sha == local_sha:
            to_stage.append(path)
    if to_stage:
        _git(repo_dir, "add", "--", *to_stage)
    try:
        _git(repo_dir, "merge", "--ff-only", "--quiet", tracking)
        log(f"  Local '{branch}' fast-forwarded to {remote}/{branch}.")
    except GitError as e:
        if to_stage:
            _git(repo_dir, "reset", "--quiet", "--", *to_stage, check=False)
        log(f"  NOTE: could not fast-forward local '{branch}' ({e}). "
            "Published data is safe on the remote; pull when convenient.")


def _safe_sync(repo_dir, remote, branch, data_rel, index, log):
    """Run _sync_local_checkout, logging (never raising) on failure.

    The data is already on the remote at this point, so a local sync
    problem must not trigger a publish retry or fail the run.
    """
    try:
        _sync_local_checkout(repo_dir, remote, branch, data_rel, index, log)
    except (GitError, OSError) as e:
        log(f"  NOTE: data is published, but updating the local checkout failed: {e}")


def publish_dashboard_data(repo_dir=DEFAULT_REPO_DIR, data_rel=DATA_REL, remote="origin",
                           branch="main", attempts=3, retry_delay=15, timeout=120,
                           log=print):
    """Publish pending dashboard data files to ``remote/branch``.

    Args:
        repo_dir: Path inside the git repository.
        data_rel: Repo-relative data directory.
        remote: Remote to publish to.
        branch: Branch GitHub Pages builds from.
        attempts: Fetch/build/push attempts before giving up for this run.
        retry_delay: Seconds to wait between attempts.
        timeout: Per-git-command timeout in seconds.
        log: Callable used for progress and error messages.

    Returns:
        True if the remote is up to date with local data, False otherwise.
        Never raises for git or network failures; they are logged instead.
    """
    try:
        top = _git(repo_dir, "rev-parse", "--show-toplevel", timeout=timeout).strip()
        _git(top, "remote", "get-url", remote, timeout=timeout)
    except GitError as e:
        log(f"  ERROR: cannot publish dashboard data: {e}")
        return False

    tracking = f"refs/remotes/{remote}/{branch}"
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            _git(top, "fetch", "--quiet", "--no-tags", remote,
                 f"+refs/heads/{branch}:{tracking}", timeout=timeout)
            base = _git(top, "rev-parse", "--verify", f"{tracking}^{{commit}}").strip()
            pending = _pending_paths(top, base, data_rel)
            commit, index, published = _build_commit(top, base, data_rel, pending, log)
            if commit is None:
                log(f"  Dashboard data already up to date on {remote}/{branch}.")
                _safe_sync(top, remote, branch, data_rel, index, log)
                return True
            _git(top, "push", "--quiet", remote, f"{commit}:refs/heads/{branch}",
                 timeout=timeout)
            _git(top, "update-ref", tracking, commit)
            log(f"  Published {len(published)} file(s) to {remote}/{branch} "
                f"({commit[:10]}): {', '.join(os.path.basename(p) for p in published)}")
            _safe_sync(top, remote, branch, data_rel, index, log)
            return True
        except GitError as e:
            last_error = e
            log(f"  Publish attempt {attempt}/{attempts} failed: {e}")
            if attempt < attempts:
                time.sleep(retry_delay)
        except OSError as e:
            last_error = e
            log(f"  Publish attempt {attempt}/{attempts} failed: {e}")
            break

    log(f"  ERROR: dashboard data NOT published ({last_error}). The files stay "
        "on disk and will be retried on the next run, or run "
        "`python dashboard_publisher.py` by hand.")
    return False


if __name__ == "__main__":
    sys.exit(0 if publish_dashboard_data() else 1)
