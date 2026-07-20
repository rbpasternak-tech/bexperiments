#!/usr/bin/env python3
"""Watchtower: live dashboard of Claude Code activity across the monorepo.

Scans ~/.claude/projects/ for session transcripts belonging to this repo
(the root and every project subfolder), and renders a self-refreshing
terminal view of:

  - each session that was active recently, with its opening prompt
  - subagents spawned by each session (running or recently finished)
  - loop markers (a ScheduleWakeup call in the transcript tail means the
    session has a pending self-scheduled wakeup)
  - workflow markers (a Workflow tool call in the transcript tail)

Liveness is inferred from transcript file mtimes: Claude Code appends to
the session .jsonl on every turn, and each subagent writes its own
subagents/agent-*.jsonl, so a recent mtime means "running right now".

Usage: python3 watchtower.py            (refreshes every 2 seconds)
       python3 watchtower.py --once     (print one snapshot and exit)
"""

import json
import sys
import time
from pathlib import Path

REFRESH_SECONDS = 2
ACTIVE_SECONDS = 90            # mtime newer than this = running now
SESSION_WINDOW_SECONDS = 6 * 3600   # hide sessions idle longer than this
AGENT_DONE_WINDOW_SECONDS = 15 * 60  # show finished agents this long
TAIL_BYTES = 64 * 1024

REPO_ROOT = Path(__file__).resolve().parent
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
REPO_PREFIX = str(REPO_ROOT).replace("/", "-")

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"

_title_cache = {}


def humanize(seconds):
    """Format a duration in seconds as a short human string like 3m or 2h."""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    return f"{int(seconds // 3600)}h{int(seconds % 3600 // 60):02d}m"


def read_tail(path):
    """Return the last TAIL_BYTES of a file as text, ignoring bad bytes."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def session_title(path):
    """Return the first user prompt of a session transcript, cached."""
    cached = _title_cache.get(path)
    if cached is not None:
        return cached
    title = ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "user":
                    continue
                content = (entry.get("message") or {}).get("content")
                if isinstance(content, str):
                    title = content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            title = block.get("text", "")
                            break
                break
    except OSError:
        pass
    title = " ".join(title.split())[:70]
    _title_cache[path] = title
    return title


def scan_subagents(session_dir, now):
    """Return info dicts for subagent transcripts under a session directory."""
    agents = []
    subagents_dir = session_dir / "subagents"
    if not subagents_dir.is_dir():
        return agents
    for transcript in sorted(subagents_dir.glob("agent-*.jsonl")):
        try:
            age = now - transcript.stat().st_mtime
        except OSError:
            continue
        if age > AGENT_DONE_WINDOW_SECONDS:
            continue
        meta = {}
        meta_path = transcript.with_suffix("").with_suffix(".meta.json")
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
        agents.append({
            "type": meta.get("agentType", "agent"),
            "description": meta.get("description", transcript.stem),
            "age": age,
            "running": age <= ACTIVE_SECONDS,
        })
    agents.sort(key=lambda a: a["age"])
    return agents


def scan_sessions(project_dir, now):
    """Return info dicts for recently active sessions in a project dir."""
    sessions = []
    for transcript in project_dir.glob("*.jsonl"):
        try:
            age = now - transcript.stat().st_mtime
        except OSError:
            continue
        if age > SESSION_WINDOW_SECONDS:
            continue
        tail = read_tail(transcript)
        sessions.append({
            "id": transcript.stem[:8],
            "title": session_title(transcript),
            "age": age,
            "running": age <= ACTIVE_SECONDS,
            "loop": '"ScheduleWakeup"' in tail,
            "workflow": '"name":"Workflow"' in tail or '"name": "Workflow"' in tail,
            "agents": scan_subagents(transcript.parent / transcript.stem, now),
        })
    sessions.sort(key=lambda s: s["age"])
    return sessions


def gather(now):
    """Map project name -> session list for every repo project dir."""
    projects = {}
    if not CLAUDE_PROJECTS.is_dir():
        return projects
    for project_dir in sorted(CLAUDE_PROJECTS.iterdir()):
        name = project_dir.name
        if name == REPO_PREFIX:
            label = "repo"
        elif name.startswith(REPO_PREFIX + "-"):
            label = name[len(REPO_PREFIX) + 1:]
        else:
            continue
        sessions = scan_sessions(project_dir, now)
        if sessions:
            projects[label] = sessions
    return projects


def render(projects, now):
    """Return the dashboard as a list of lines."""
    clock = time.strftime("%H:%M:%S", time.localtime(now))
    lines = [
        f"{BOLD}WATCHTOWER{RESET} — bexperiments   {DIM}{clock}, "
        f"refreshes every {REFRESH_SECONDS}s, Ctrl-C to quit{RESET}",
        "",
    ]
    if not projects:
        lines.append(f"{DIM}No Claude sessions active in the last "
                     f"{SESSION_WINDOW_SECONDS // 3600}h.{RESET}")
        return lines
    for label, sessions in projects.items():
        any_running = any(s["running"] for s in sessions)
        dot = f"{GREEN}●{RESET}" if any_running else f"{DIM}○{RESET}"
        lines.append(f"{dot} {BOLD}{label}{RESET}")
        for s in sessions:
            dot = f"{GREEN}●{RESET}" if s["running"] else f"{DIM}○{RESET}"
            state = (f"{GREEN}active {humanize(s['age'])} ago{RESET}"
                     if s["running"]
                     else f"{DIM}idle {humanize(s['age'])}{RESET}")
            tags = ""
            if s["loop"]:
                tags += f"  {YELLOW}⟳ loop{RESET}"
            if s["workflow"]:
                tags += f"  {CYAN}⚙ workflow{RESET}"
            title = f' "{s["title"]}"' if s["title"] else ""
            lines.append(f"  {dot} {s['id']}{title}  {state}{tags}")
            for agent in s["agents"]:
                dot = (f"{GREEN}●{RESET}" if agent["running"]
                       else f"{DIM}○{RESET}")
                state = (f"{GREEN}running{RESET}" if agent["running"]
                         else f"{DIM}done {humanize(agent['age'])} ago{RESET}")
                lines.append(f"      {dot} {agent['type']} — "
                             f"{agent['description'][:60]}  {state}")
        lines.append("")
    return lines


def main():
    """Run the dashboard loop (or a single snapshot with --once)."""
    once = "--once" in sys.argv
    while True:
        now = time.time()
        output = "\n".join(render(gather(now), now))
        if once:
            print(output)
            return
        # Home the cursor and clear to end of screen: less flicker than clear.
        sys.stdout.write("\x1b[H\x1b[J" + output + "\n")
        sys.stdout.flush()
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
