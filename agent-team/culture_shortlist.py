"""NYC Culture Shortlist: catch the weekly self-sent email, offer its picks in
Telegram, and file the approved ones to To-try/Culture.md.

Flow
- Detection: every CHECK_EVERY_MINUTES between CHECK_START and CHECK_END the
  polling loop runs ONE targeted read-only Gmail search (QUERY). Forwards,
  replies and anything with "Test" in the subject are ignored. Each message
  id is handled exactly once (state file STATE_NAME in the state dir, key "handled").
- Approval: the numbered picks (plus the optional NEXT WEEK TO WATCH item)
  are posted by Jeeves; Rebecca replies "add 1 and 3", "add 2-4", "add all",
  "all but 2" or "none". The reply is consumed here, before the persona
  router, so it never reaches the general chat handler. An unanswered list
  expires quietly after PENDING_HOURS and is mentioned once in the next
  morning triage.
- Filing: approved picks are appended (append-only, deduped by URL or by
  normalized title against every existing line, hand-written ones
  included) to To-try/Culture.md via Vault.append_culture_lines.
- Auto-mode nudge: offered/approved are tallied; after AUTO_MIN_SHORTLISTS
  shortlists with >= AUTO_APPROVAL_RATE approved, the bot proposes automatic
  filing once. It never switches by itself.

Preview (no Telegram, no vault write, no state write):
  python culture_shortlist.py --preview <gmail-message-id> --reply "add 1 and 3"
"""

import argparse
import re
import threading
from datetime import datetime, timedelta, time as dtime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

STATE_NAME = "culture-shortlist.json"  # in the state dir: ~/Library/Application Support/agent-team/
CULTURE_NOTE = "To-try/Culture.md"
QUERY = 'from:me subject:"NYC Culture Shortlist" newer_than:2d'
CHECK_EVERY_MINUTES = 30
CHECK_START, CHECK_END = dtime(7, 0), dtime(22, 0)
PENDING_HOURS = 48
AUTO_MIN_SHORTLISTS = 3
AUTO_APPROVAL_RATE = 0.8
PERSONA = ("🎩", "Jeeves")

_LOCK = threading.Lock()
_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_DAY = r"(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+)?"
_CLOSING_RE = re.compile(
    rf"\b(?:through|thru|until|till|runs only through|closes)\s+({_DAY}{_MONTHS}\s+\d{{1,2}})", re.I
)
_DATE_RE = re.compile(rf"({_DAY}{_MONTHS}\s+\d{{1,2}}(?:,?\s+\d{{1,2}}(?::\d\d)?\s*(?:[–-]\s*\d{{1,2}}(?::\d\d)?)?\s*[AP]M)?)", re.I)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_PICK_RE = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")
_ABBREV = {"jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
           "nov", "dec", "st", "mt", "dr", "mr", "ms", "mrs", "no", "vs"}
_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or",
          "the", "to", "vs", "with", "from"}


# --- state -----------------------------------------------------------------

def load_state(state_store):
    """Read the shortlist state (handled ids, pending list, tally)."""
    data = state_store._read_json(state_store.state_dir / STATE_NAME, {})
    data.setdefault("handled", {})
    data.setdefault("pending", None)
    data.setdefault("expired_unannounced", [])
    data.setdefault("tally", {"shortlists": 0, "offered": 0, "approved": 0, "expired": 0})
    data.setdefault("auto_proposal_sent", None)
    data.setdefault("first_live_caught", None)
    return data


def save_state(state_store, data):
    """Persist the shortlist state atomically."""
    state_store._write_json(state_store.state_dir / STATE_NAME, data)


# --- parsing ---------------------------------------------------------------

def _title_case(heading):
    """'MoMA — NEW YOKO ONO + FRIDA/DIEGO' -> 'MoMA — New Yoko Ono + Frida/Diego'."""
    words, out = heading.split(), []
    for i, word in enumerate(words):
        def fix(part, first):
            if not part.isupper() or not any(c.isalpha() for c in part):
                return part  # mixed case (MoMA) or symbols: keep
            if not re.search(r"[AEIOU]", part):
                return part  # vowelless acronyms: DJ, NYC, MCNY
            low = part.lower()
            if not first and low in _SMALL:
                return low
            return low[:1].upper() + low[1:]
        prev = words[i - 1] if i else ""
        first = i == 0 or prev in ("—", "–", "-", ":")
        out.append("/".join(fix(p, first) for p in word.split("/")))
    return " ".join(out)


def _first_sentence(text):
    """First sentence, not fooled by 'Sept. 6' style abbreviations."""
    for match in re.finditer(r"\.\s+(?=[A-Z0-9])", text):
        before = re.findall(r"([A-Za-z]+)$", text[: match.start()])
        if before and before[0].lower() in _ABBREV:
            continue
        return text[: match.start() + 1].strip()
    return text.strip()


def _pick_fields(title, body_lines, number, optional=False):
    """Build one pick from its heading and body lines."""
    body = " ".join(l.strip() for l in body_lines if l.strip())
    urls = _URL_RE.findall(body)
    url = urls[-1].rstrip(".,;:") if urls else ""
    para = _URL_RE.sub("", body).strip()
    closing = _CLOSING_RE.search(para)
    first = _first_sentence(para)
    dates = first.rstrip(".") if _DATE_RE.search(first) and len(first) <= 90 else ""
    if not dates:
        found = _DATE_RE.search(para)
        dates = found.group(1) if found else ""
    return {
        "n": number,
        "title": title,
        "dates": dates,
        "closing": closing.group(1) if closing else "",
        "url": url,
        "optional": optional,
        "summary": para,
    }


def parse_shortlist(text, fallback_date=None):
    """Parse the email's plain text into {'date': 'YYYY-MM-DD', 'picks': [...]}."""
    lines = text.replace("\r", "").splitlines()
    date_str = fallback_date or ""
    head = re.search(r"SHORTLIST\s*[—–-]\s*([A-Za-z]+ \d{1,2}, \d{4})", text, re.I)
    if head:
        try:
            date_str = datetime.strptime(head.group(1).title(), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    picks, current, body = [], None, []
    section = None
    extra = {"HOW I'D SEQUENCE IT": [], "NEXT WEEK TO WATCH": []}

    def flush():
        if current:
            picks.append(_pick_fields(current[1], body, current[0]))

    for line in lines:
        norm = line.strip().upper().replace("’", "'")
        if norm in extra:
            flush()
            current, body, section = None, [], norm
            continue
        if section:
            extra[section].append(line)
            continue
        match = _PICK_RE.match(line)
        if match and (match.group(2).isupper() or "—" in match.group(2)):
            flush()
            current, body = (int(match.group(1)), _title_case(match.group(2))), []
        elif current:
            body.append(line)
    flush()
    watch = " ".join(l.strip() for l in extra["NEXT WEEK TO WATCH"] if l.strip())
    if watch:
        first = _first_sentence(_URL_RE.sub("", watch)).rstrip(".")
        # "MCNY has Poetry After Dark on Wednesday, Sept. 9 at 6:30 PM as part of…"
        name = re.split(
            r"\s+(?:on|this|next|at)\s+(?=(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)|\d)|\s+as part of|,",
            first, maxsplit=1)[0]
        name = re.sub(r"^(.*?)\s+(?:has|hosts|presents|is hosting|offers)\s+(.*)$", r"\1 — \2", name)
        title = (name if len(name) <= 80 else name[:77] + "…").strip()
        pick = _pick_fields(title, [watch], len(picks) + 1, optional=True)
        picks.append(pick)
    return {"date": date_str, "picks": picks,
            "sequence": " ".join(l.strip() for l in extra["HOW I'D SEQUENCE IT"] if l.strip())}


# --- rendering -------------------------------------------------------------

def _pretty_date(date_str):
    """'2026-09-03' -> 'Thu Sep 3'."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %b %-d")
    except ValueError:
        return date_str


def render_offer(parsed):
    """The Telegram message offering the picks."""
    emoji, name = PERSONA
    lines = [f"{emoji} {name}:",
             f"The NYC Culture Shortlist for {_pretty_date(parsed['date'])} has arrived. "
             "Which shall I file to To-try/Culture?", ""]
    for p in parsed["picks"]:
        label = " (next week to watch)" if p["optional"] else ""
        when = f"through {p['closing']}" if p["closing"] else p["dates"]
        lines.append(f"{p['n']}. {p['title']}{label}")
        detail = " · ".join(x for x in (when, p["url"]) if x)
        if detail:
            lines.append(f"   {detail}")
    lines += ["", 'Reply "add 1 and 3", "add 2-4", "add all" or "none". '
              f"Unanswered, it lapses quietly after {PENDING_HOURS} hours."]
    return "\n".join(lines)


def format_line(pick, shortlist_date):
    """'- [ ] Title — URL (through DATE) _(shortlist YYYY-MM-DD)_'."""
    parts = [f"- [ ] {pick['title']}"]
    if pick["url"]:
        parts.append(f" — {pick['url']}")
    if pick["closing"]:
        parts.append(f" (through {pick['closing']})")
    elif pick["dates"]:
        parts.append(f" ({pick['dates']})")
    parts.append(f" _(shortlist {shortlist_date})_")
    return "".join(parts)


# --- reply parsing ---------------------------------------------------------

# "skip"/"no" are deliberately absent: "skip" answers a clip-caption prompt,
# and a bare "no" may answer some other question.
_NONE_RE = re.compile(r"^\s*(?:add\s+|file\s+)?(?:none|none of (?:them|those|these|it))"
                      r"(?:,?\s*thanks?(?: you)?)?\s*[.!]?\s*$", re.I)
_VERB_RE = re.compile(r"^\s*(?:add|file|save|keep|pick|take)\b", re.I)
_ALL_RE = re.compile(r"^\s*(?:add\s+|file\s+|save\s+|keep\s+)?(?:them\s+)?all(?:\s+of\s+(?:them|those|these))?"
                     r"(?:\s+(?:but|except|minus|apart from)\s+(?P<except>[\d\s,&+and\-–to#]+))?\s*[.!]?\s*$", re.I)
_NUMS_RE = re.compile(r"^\s*(?:add|file|save|keep|pick|take)?\s*(?:#|numbers?\s+)?"
                      r"(?P<nums>\d{1,2}(?:\s*(?:-|–|to|through)\s*\d{1,2})?"
                      r"(?:\s*(?:,|&|\+|and|plus|\s)\s*#?\d{1,2}(?:\s*(?:-|–|to|through)\s*\d{1,2})?)*)"
                      r"\s*[.!]?\s*$", re.I)


def _expand(numbers_text):
    """'1, 3-5 and 7' -> {1, 3, 4, 5, 7}."""
    chosen = set()
    for a, b in re.findall(r"(\d{1,2})(?:\s*(?:-|–|to|through)\s*(\d{1,2}))?", numbers_text):
        lo, hi = int(a), int(b or a)
        if lo > hi:
            lo, hi = hi, lo
        chosen.update(range(lo, hi + 1))
    return chosen


def parse_reply(text, count, bare_ok=True):
    """Interpret a reply to a pending shortlist.

    Returns None when the text is not a shortlist reply (it then goes to the
    normal chat handler), else ('ok', sorted numbers) or ('bad', message).
    Bare numbers ("1 3") count only when bare_ok — i.e. the offer is the
    bot's latest message; otherwise a verb ("add 1 3") is required.
    """
    if _NONE_RE.match(text):
        return ("ok", [])
    match = _ALL_RE.match(text)
    if match:
        chosen = set(range(1, count + 1)) - _expand(match.group("except") or "")
        return ("ok", sorted(chosen))
    match = _NUMS_RE.match(text)
    if not match or (not bare_ok and not _VERB_RE.match(text)):
        return None
    chosen = _expand(match.group("nums"))
    bad = sorted(n for n in chosen if not 1 <= n <= count)
    if bad:
        return ("bad", f"There are only {count} picks (1–{count}); "
                       f"{', '.join(map(str, bad))} isn't one. "
                       'Reply e.g. "add 1 and 3", "add all" or "none".')
    return ("ok", sorted(chosen))


# --- dedupe and filing -----------------------------------------------------

def _norm_url(url):
    """Comparable URL: lowercased host without www, no query/fragment/trailing slash."""
    parts = urlsplit(url.strip().rstrip(".,;:"))
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}".lower()


def _norm_title(text):
    """Lowercase alphanumeric words only."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower().replace("&", " and ")))


def _line_title(line):
    """The title part of an existing Culture.md line (hand-written or ours)."""
    text = re.sub(r"^\s*[-*]\s*(\[[ xX]\]\s*)?", "", line)
    text = _URL_RE.sub(" ", text)
    text = re.sub(r"_\(shortlist [^)]*\)_", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.split(" — ")[0] if " — " in text and not _URL_RE.search(line) else text
    return _norm_title(text.replace("—", " "))


def plan_filing(existing_text, picks, shortlist_date):
    """Split picks into (lines_to_append, skipped_titles) against the note."""
    urls = {_norm_url(u) for u in _URL_RE.findall(existing_text)}
    titles = {_line_title(l) for l in existing_text.splitlines() if l.strip()}
    titles.discard("")
    fresh, skipped = [], []
    for pick in picks:
        key_t = _norm_title(pick["title"])
        dup = (pick["url"] and _norm_url(pick["url"]) in urls) or (
            not pick["url"] and key_t in titles)
        if dup:
            skipped.append(pick["title"])
            continue
        fresh.append(format_line(pick, shortlist_date))
        if pick["url"]:
            urls.add(_norm_url(pick["url"]))
        titles.add(key_t)
    return fresh, skipped


def receipt(filed_picks, skipped):
    """One-line Telegram receipt."""
    emoji, name = PERSONA
    parts = []
    if filed_picks:
        parts.append("Filed to To-try/Culture: " + "; ".join(filed_picks) + ".")
    else:
        parts.append("Nothing new filed.")
    if skipped:
        parts.append("Skipped (already there): " + "; ".join(skipped) + ".")
    return f"{emoji} {name}: " + " ".join(parts)


# --- live flow -------------------------------------------------------------

def _is_shortlist(msg):
    """True for a real shortlist: not a forward/reply, no 'Test' in subject."""
    subject = msg.get("subject", "").strip()
    if re.match(r"^(?:re|fwd?|fw)\s*:", subject, re.I):
        return False
    if re.search(r"\btest\b", subject, re.I):
        return False
    return subject.lower().startswith("nyc culture shortlist")


def _resolve(data, chosen_count, offered, expired=False):
    """Update the tally when a pending list is answered or expires."""
    t = data["tally"]
    t["shortlists"] += 1
    t["offered"] += offered
    t["approved"] += chosen_count
    if expired:
        t["expired"] = t.get("expired", 0) + 1


def _auto_nudge(data):
    """The one-time auto-filing proposal, or None."""
    t = data["tally"]
    if data.get("auto_proposal_sent") or t["shortlists"] < AUTO_MIN_SHORTLISTS or not t["offered"]:
        return None
    rate = t["approved"] / t["offered"]
    if rate < AUTO_APPROVAL_RATE:
        return None
    data["auto_proposal_sent"] = datetime.now().isoformat(timespec="seconds")
    emoji, name = PERSONA
    return (f"{emoji} {name}: Over {t['shortlists']} culture shortlists you've approved "
            f"{t['approved']} of {t['offered']} picks ({rate:.0%}). Shall I simply file "
            "every pick automatically from now on and send you the receipt? "
            "Nothing changes unless you say so.")


def expire_if_due(data, now):
    """Expire a pending list older than PENDING_HOURS (quietly)."""
    pending = data.get("pending")
    if not pending:
        return False
    posted = datetime.fromisoformat(pending["posted_at"])
    if now - posted < timedelta(hours=PENDING_HOURS):
        return False
    data["handled"].setdefault(pending["message_id"], {})["status"] = "expired"
    data["expired_unannounced"].append(
        {"shortlist_date": pending["shortlist_date"], "picks": len(pending["picks"]),
         "expired_at": now.isoformat(timespec="seconds")})
    _resolve(data, 0, len(pending["picks"]), expired=True)
    data["pending"] = None
    return True


def poll(ctx, telegram, chat_id, gmail, now=None, force=False):
    """Run the check if it is due; post any new shortlist. Never raises."""
    now = now or datetime.now()
    state_store = ctx["state"]
    with _LOCK:
        data = load_state(state_store)
        changed = expire_if_due(data, now)
        last = data.get("last_check")
        due = force or (
            CHECK_START <= now.time() <= CHECK_END
            and (not last or now - datetime.fromisoformat(last) >= timedelta(minutes=CHECK_EVERY_MINUTES)))
        nudge = _auto_nudge(data) if changed else None
        if not due:
            if changed:
                save_state(state_store, data)
            if nudge:
                telegram.send_message(chat_id, nudge)
            return None
        data["last_check"] = now.isoformat(timespec="seconds")
        try:
            msgs = [m for m in gmail.search(QUERY, 10) if _is_shortlist(m)]
        except Exception as exc:
            data["last_error"] = f"{now:%Y-%m-%d %H:%M} {type(exc).__name__}: {exc}"
            save_state(state_store, data)
            print(f"[culture] Gmail check failed: {exc}", flush=True)
            return None
        new = [m for m in msgs if m["id"] not in data["handled"]]
        posted = None
        for msg in reversed(new):  # oldest first; the newest ends up pending
            body = gmail.read(msg["id"], max_chars=20000)
            try:
                received = parsedate_to_datetime(msg["date"]).astimezone().replace(tzinfo=None)
            except (TypeError, ValueError):
                received = now
            parsed = parse_shortlist(body.split("\n\n", 1)[-1], received.date().isoformat())
            record = {"subject": msg["subject"], "received": received.isoformat(timespec="minutes"),
                      "caught_at": now.isoformat(timespec="seconds"), "picks": len(parsed["picks"])}
            if not parsed["picks"]:
                record["status"] = "unparsed"
                data["handled"][msg["id"]] = record
                telegram.send_message(chat_id, f"{PERSONA[0]} {PERSONA[1]}: A culture shortlist "
                                      f"arrived ({msg['subject']}) but I couldn't find numbered picks in it.")
                continue
            if data.get("pending"):  # a newer list supersedes an unanswered one
                old = data["pending"]
                data["handled"].setdefault(old["message_id"], {})["status"] = "superseded"
                data["expired_unannounced"].append({"shortlist_date": old["shortlist_date"],
                                                    "picks": len(old["picks"]),
                                                    "expired_at": now.isoformat(timespec="seconds")})
                _resolve(data, 0, len(old["picks"]), expired=True)
            record["status"] = "posted"
            data["handled"][msg["id"]] = record
            data["pending"] = {"message_id": msg["id"], "shortlist_date": parsed["date"],
                               "posted_at": now.isoformat(timespec="seconds"), "picks": parsed["picks"]}
            if not data.get("first_live_caught"):
                data["first_live_caught"] = dict(record, message_id=msg["id"])
            text = render_offer(parsed)
            telegram.send_message(chat_id, text)
            state_store.append_history(chat_id, PERSONA[1], text.split("\n", 1)[1])
            posted = msg["id"]
            print(f"[culture] posted shortlist {parsed['date']} ({msg['id']}, {len(parsed['picks'])} picks)", flush=True)
        save_state(state_store, data)
        if nudge:
            telegram.send_message(chat_id, nudge)
        return posted


def handle_reply(text, ctx, telegram, chat_id, now=None):
    """Consume a reply to the pending shortlist. True when consumed."""
    now = now or datetime.now()
    state_store = ctx["state"]
    with _LOCK:
        data = load_state(state_store)
        if expire_if_due(data, now):
            save_state(state_store, data)
        pending = data.get("pending")
        if not pending:
            return False
        history = state_store.get_history(chat_id)
        last_bot = next((h["text"] for h in reversed(history) if h["speaker"] != "user"), "")
        bare_ok = last_bot.startswith("The NYC Culture Shortlist for")
        result = parse_reply(text, len(pending["picks"]), bare_ok=bare_ok)
        if result is None:
            return False
        state_store.append_history(chat_id, "user", text)
        kind, value = result
        if kind == "bad":
            telegram.send_message(chat_id, f"{PERSONA[0]} {PERSONA[1]}: {value}")
            return True
        chosen = [p for p in pending["picks"] if p["n"] in value]
        vault = ctx["vault"]
        existing = vault.read_culture_note()
        if existing is None:
            telegram.send_message(chat_id, f"{PERSONA[0]} {PERSONA[1]}: Couldn't read "
                                  f"{CULTURE_NOTE} ({vault.availability_error() or 'unavailable'}); "
                                  "nothing filed — the list is still open, reply again later.")
            return True
        lines, skipped = plan_filing(existing, chosen, pending["shortlist_date"])
        status = vault.append_culture_lines(lines) if lines else "nothing to append"
        filed = [p["title"] for p in chosen if p["title"] not in skipped]
        msg = receipt(filed, skipped) if chosen else f"{PERSONA[0]} {PERSONA[1]}: Very good — none filed."
        if status.startswith(("Vault not", "Error", "Refused")):
            msg = f"{PERSONA[0]} {PERSONA[1]}: Filing failed ({status}); the list is still open."
            telegram.send_message(chat_id, msg)
            return True
        rec = data["handled"].setdefault(pending["message_id"], {})
        rec.update(status="answered", answered_at=now.isoformat(timespec="seconds"),
                   approved=[p["n"] for p in chosen], filed=len(lines), skipped=len(skipped))
        _resolve(data, len(chosen), len(pending["picks"]))
        data["pending"] = None
        nudge = _auto_nudge(data)
        save_state(state_store, data)
        telegram.send_message(chat_id, msg)
        state_store.append_history(chat_id, PERSONA[1], msg.split(": ", 1)[1])
        if nudge:
            telegram.send_message(chat_id, nudge)
        return True


def triage_note(state_store):
    """A line for the morning triage about lists that expired unanswered."""
    data = load_state(state_store)
    items = data.get("expired_unannounced") or []
    if not items:
        return ""
    desc = "; ".join(f"the {_pretty_date(i['shortlist_date'])} list ({i['picks']} picks)" for i in items)
    return ("CULTURE SHORTLIST NOTE: " + desc + " expired without a reply, so nothing "
            "was filed. Mention it once, in one line, at the end of Part 1.")


def mark_triage_announced(state_store):
    """Clear the expired-unannounced list after the triage went out."""
    with _LOCK:
        data = load_state(state_store)
        if data.get("expired_unannounced"):
            data["expired_unannounced"] = []
            save_state(state_store, data)


def seed_handled(state_store, entries):
    """Mark existing messages handled without posting them ({id: subject})."""
    with _LOCK:
        data = load_state(state_store)
        for mid, subject in entries.items():
            data["handled"].setdefault(mid, {"subject": subject, "status": "seeded",
                                             "caught_at": datetime.now().isoformat(timespec="seconds")})
        save_state(state_store, data)
        return data


# --- preview ---------------------------------------------------------------

def preview(message_id, reply_text, config_path=Path(__file__).with_name("config.yaml")):
    """Parse a real email, render the offer, simulate a reply. Read-only."""
    import yaml
    from gmail_reader import GmailReader
    from vault import Vault
    cfg = yaml.safe_load(config_path.read_text())
    gmail = GmailReader(cfg.get("gmail_token_path"))
    body = gmail.read(message_id, max_chars=20000)
    parsed = parse_shortlist(body.split("\n\n", 1)[-1])
    print("=" * 18, "TELEGRAM MESSAGE (not sent)", "=" * 18)
    print(render_offer(parsed))
    print("=" * 18, "PARSED PICKS", "=" * 18)
    for p in parsed["picks"]:
        print(f"{p['n']}. title={p['title']!r}\n   dates={p['dates']!r} closing={p['closing']!r}"
              f"\n   url={p['url']!r} optional={p['optional']}")
    result = parse_reply(reply_text, len(parsed["picks"]))
    print("=" * 18, f"SIMULATED REPLY {reply_text!r} -> {result}", "=" * 18)
    if not result or result[0] != "ok":
        return
    existing = Vault(cfg.get("vault_path")).read_culture_note() or ""
    chosen = [p for p in parsed["picks"] if p["n"] in result[1]]
    lines, skipped = plan_filing(existing, chosen, parsed["date"])
    print(f"Lines that WOULD be appended to {CULTURE_NOTE} (nothing written):")
    print("\n".join(lines) or "(none)")
    print("Skipped as duplicates:", skipped or "none")
    print("Receipt:", receipt([p["title"] for p in chosen if p["title"] not in skipped], skipped))
    # Dedupe vs a hand-written line: a pick whose URL matches her own
    # "Krasner & Pollak https://www.metmuseum.org/..." line (with www/slash/
    # query variations) and a link-less pick whose title matches one.
    probe = [dict(chosen[0] if chosen else parsed["picks"][0], n=98, title="Met — Krasner and Pollock",
                  url="https://metmuseum.org/exhibitions/krasner-and-pollock-past-continuous/?utm=x"),
             dict(parsed["picks"][0], n=99, title="A Few Good Men", url="", closing="", dates="Nov 1")]
    p_lines, p_skipped = plan_filing(existing, probe, parsed["date"])
    print("Dedupe check vs hand-written lines:", f"{len(p_lines)} new, skipped {p_skipped}")
    # Dedupe self-check: re-running against the note + these lines skips all.
    again, again_skipped = plan_filing(existing + "\n" + "\n".join(lines), chosen, parsed["date"])
    print("Dedupe re-run (same reply again):", f"{len(again)} new, {len(again_skipped)} skipped")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--preview", metavar="MESSAGE_ID", required=True)
    ap.add_argument("--reply", default="add 1 and 3")
    args = ap.parse_args()
    preview(args.preview, args.reply)
