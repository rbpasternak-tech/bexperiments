"""Extract structured trend data from digest content for the dashboard."""

import json
import os
import time
from datetime import datetime

from dashboard_publisher import (
    atomic_write_json,
    index_entry_from_meta,
    read_json_file,
    rebuild_index_from_dir,
    sort_index_entries,
)

# Keys the dashboard reads; missing or malformed ones are normalized so one
# bad extraction cannot break the page.
LIST_KEYS = (
    "topics",
    "ai_economy_events",
    "regulatory_events",
    "legal_tech_signals",
    "source_contributions",
)
MAX_OUTPUT_TOKENS = 16000

CANONICAL_TOPICS = """\
Use these canonical topic names whenever content matches. Only create a new topic name if none of these fit:
- "AI Agents" — autonomous AI agents, agentic workflows, computer use, multi-agent systems
- "Large Language Models" — LLMs, foundation models, model releases, model benchmarks
- "Legal AI Adoption" — law firms using AI, lawyer AI usage, legal AI statistics, in-house AI
- "Legal Tech Funding" — investments, funding rounds, valuations, M&A in legal tech
- "Contract Analysis AI" — contract review, redlining, CLM, NDA tools, document drafting AI
- "E-Discovery & Litigation AI" — ediscovery, litigation support, document review, legal hold
- "Compliance Technology" — RegTech, compliance automation, AML, KYC, audit tools
- "AI Regulation" — government AI policy, AI laws, executive orders on AI, AI legislation
- "Data Privacy" — GDPR, CCPA, privacy laws, data protection rulings, surveillance
- "Law Firm Technology" — BigLaw tech adoption, practice management, firm IT, DMS
- "Legal Practice Innovation" — legal ops, new service delivery, legal innovation, legal design
- "Enterprise AI" — AI in enterprise, corporate AI adoption, B2B AI, AI strategy
- "AI Safety & Ethics" — AI safety, bias, responsible AI, AI ethics, alignment
- "Open Source AI" — open source models, Llama, Mistral, open weights, community AI
- "Workforce & Jobs" — AI job displacement, hiring trends, legal jobs, skills, reskilling
- "Cybersecurity" — security threats, breaches, AI security, ransomware
- "Court Technology" — courts using AI, judicial AI, e-filing, court systems
- "IP & Copyright" — AI copyright, patent AI, IP law, training data rights
- "Startup Ecosystem" — new AI/legal tech startups, accelerators, incubators, founders
- "AI Infrastructure" — compute, GPUs, cloud AI, data centers, inference costs
"""

EXTRACTION_PROMPT = """\
You are a structured data extraction system. You will receive tech and legal tech newsletter content and RSS articles. Extract structured data for a trends dashboard.

Return ONLY valid JSON matching the schema below. No text before or after the JSON.

""" + CANONICAL_TOPICS + """

Extract:

1. **topics**: Distinct topics across all sources. Each:
   - "name": Use a canonical topic name from the list above whenever possible. Only create new names for truly novel topics.
   - "category": One of: "ai", "legal_tech", "regulation", "startup", "enterprise", "open_source", "security", "data_privacy", "workforce"
   - "mention_count": How many distinct articles mention this
   - "sentiment": "positive", "neutral", "negative", or "mixed"
   - "representative_headlines": 1-3 actual headlines

2. **ai_economy_events**: Concrete business events. Each:
   - "type": "funding", "acquisition", "partnership", "layoff", "ipo", or "product_launch"
   - "entity": Company name
   - "amount": Display string ("$2B") or null
   - "amount_usd": Numeric value (2000000000) or null
   - "headline": One-line summary
   - "source": Source name
   - "source_url": URL or null

3. **regulatory_events**: Government/regulatory actions. Each:
   - "jurisdiction": "US", "EU", "UK", "China", "Global", or specific
   - "type": "new_regulation", "enforcement_action", "guidance", "court_ruling", "executive_order", "legislative_proposal"
   - "title": Short title
   - "summary": 1-2 sentences
   - "sentiment": "restrictive", "permissive", "neutral", or "mixed"
   - "impact_area": Array from category list above
   - "source", "source_url"

4. **legal_tech_signals**: Legal tech adoption signals. Each:
   - "type": "product_launch", "firm_adoption", "integration", "milestone"
   - "entity": Company/firm name
   - "description": What happened
   - "source", "source_url"

5. **source_contributions**: For each unique source:
   - "source_name", "source_type" ("rss" or "newsletter")
   - "article_count": Number of items from this source
   - "top_topics": 1-3 topic names this source contributed to
   - "signal_strength": "high", "medium", or "low"

6. **weekly_snapshot**:
   - "top_stories": Exactly 3 objects with "rank" (1-3), "headline", "why_it_matters" (1-2 sentences), "sources" ([{name, url}])
   - "one_to_watch": {headline, why_it_matters, sources}
   - "quick_stats": {total_articles_analyzed, funding_total_usd, new_regulations_count, product_launches_count, dominant_topic, sentiment_balance: {positive, neutral, negative}}

7. **weekly_narrative**: A 2-3 sentence synthesis of the week's dominant themes and their significance for the legal tech and AI industry. Write for a senior executive — connect the dots between stories, not just a list of events.

IMPORTANT:
- Only extract what is EXPLICITLY in the content. Do not invent data.
- Empty categories should be empty arrays.
- Normalize monetary amounts to USD with both display string and numeric value.
- Use consistent, reusable topic names across runs.
"""


def extract_trends(newsletters, rss_articles, date_start, date_end, model, output_dir):
    """Extract structured trend data and write to JSON files.

    Args:
        newsletters: List of email dicts (filtered newsletters).
        rss_articles: List of RSSArticle objects.
        date_start: datetime for start of period.
        date_end: datetime for end of period.
        model: Claude model ID.
        output_dir: Path to write JSON data files.
    """
    import anthropic  # lazy: the index helpers below work without the SDK

    content_parts = _build_content(newsletters, rss_articles)

    if not content_parts:
        print("  No content to extract trends from.")
        return

    client = anthropic.Anthropic(timeout=600.0, max_retries=5)
    prompt = "Extract structured data:\n\n" + "\n".join(content_parts)

    # Retry up to 3 times on transient API errors
    last_error = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 10 * (2 ** attempt)
                print(f"  Claude API error (attempt {attempt + 1}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
    else:
        raise RuntimeError(f"Claude API failed after 3 attempts: {last_error}") from last_error

    raw_text = "".join(
        getattr(block, "text", "") for block in (response.content or [])
    )
    if response.stop_reason == "max_tokens":
        print(f"  Warning: extraction hit max_tokens ({MAX_OUTPUT_TOKENS}); "
              "recovering what parsed.")
    extracted = parse_extraction_response(raw_text)
    if extracted is None:
        raise RuntimeError(
            f"Could not parse Claude's response as JSON (stop_reason={response.stop_reason}). "
            "Try reducing content volume or check max_tokens."
        )

    digest_id = _make_digest_id(date_end)
    source_names = sorted(set(
        [a.source for a in rss_articles]
        + [e.get("sender", "").split("<")[0].strip() for e in newsletters if e.get("sender")]
    ))

    meta = {
        "id": digest_id,
        "run_date": datetime.now().isoformat(),
        "date_range_start": date_start.strftime("%Y-%m-%d"),
        "date_range_end": date_end.strftime("%Y-%m-%d"),
        "newsletter_count": len(newsletters),
        "rss_article_count": len(rss_articles),
        "sources_analyzed": source_names,
    }
    # normalize_extraction drops any "meta" key the model invented.
    output = {"meta": meta, **normalize_extraction(extracted)}

    filename = f"digest-{digest_id}.json"
    filepath = os.path.join(output_dir, filename)
    atomic_write_json(filepath, output)
    print(f"  Wrote {filepath}")

    _update_index(output_dir, meta, filename)


def parse_extraction_response(raw_text):
    """Parse the model's JSON reply, tolerating fences, prose and truncation.

    Args:
        raw_text: Raw text returned by Claude.

    Returns:
        The parsed dict, or None if no JSON object could be recovered.
    """
    text = (raw_text or "").strip()
    start = text.find("{")
    if start == -1:
        return None
    text = text[start:]
    try:
        obj, _end = json.JSONDecoder().raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Drop a trailing code fence before attempting truncation repair.
    fence = text.rfind("```")
    if fence != -1:
        text = text[:fence].rstrip()
    return _repair_truncated_json(text)


def normalize_extraction(extracted):
    """Coerce the extracted data into the shape the dashboard expects.

    List sections that are missing or not lists become empty lists, and
    non-object items are dropped. ``weekly_snapshot`` becomes a dict.

    Args:
        extracted: Parsed dict from the model.

    Returns:
        A new, normalized dict.
    """
    result = dict(extracted)
    result.pop("meta", None)
    for key in LIST_KEYS:
        value = result.get(key)
        result[key] = [item for item in value if isinstance(item, dict)] \
            if isinstance(value, list) else []
    result["topics"] = [t for t in result["topics"] if isinstance(t.get("name"), str)]
    if not isinstance(result.get("weekly_snapshot"), dict):
        result["weekly_snapshot"] = {}
    if not isinstance(result.get("weekly_narrative"), str):
        result.pop("weekly_narrative", None)
    return result


def _build_content(newsletters, rss_articles):
    """Build content string from newsletters and RSS articles.

    Caps newsletter body at 2500 chars and RSS articles at 80 to keep
    the total input within a safe token budget.
    """
    from email_parser import extract_text

    MAX_NEWSLETTER_CHARS = 2500
    MAX_RSS_ARTICLES = 80

    parts = []

    if newsletters:
        parts.append("=== NEWSLETTER EMAILS ===\n")
        for i, email in enumerate(newsletters, 1):
            text = extract_text(email)
            if not text.strip():
                continue
            if len(text) > MAX_NEWSLETTER_CHARS:
                text = text[:MAX_NEWSLETTER_CHARS] + "\n[truncated]"
            parts.append(
                f"--- Newsletter {i} ---\n"
                f"From: {email.get('sender', 'Unknown')}\n"
                f"Subject: {email.get('subject', 'No subject')}\n"
                f"Date: {email.get('date', '')}\n\n"
                f"{text}\n"
            )

    if rss_articles:
        parts.append("\n=== RSS FEED ARTICLES ===\n")
        for article in rss_articles[:MAX_RSS_ARTICLES]:
            parts.append(
                f"--- {article.source} ---\n"
                f"Title: {article.title}\n"
                f"URL: {article.url}\n"
                f"Date: {article.published.strftime('%Y-%m-%d')}\n"
                f"Summary: {article.summary}\n"
            )

    return parts


def _repair_truncated_json(raw_text, max_attempts=400):
    """Recover the longest valid prefix of a truncated JSON object.

    Scans once, tracking string state and open brackets, and records every
    point where a value just ended (after a closing bracket, or before a
    comma). Working backwards from the end, each prefix is closed with the
    brackets still open at that point and parsed.

    Args:
        raw_text: JSON text starting with ``{`` that may be cut off.
        max_attempts: Maximum number of cut points to try.

    Returns:
        The parsed dict on success, or None.
    """
    stack = []
    in_string = False
    escaped = False
    cuts = []
    for i, ch in enumerate(raw_text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            cuts.append((i + 1, "".join(reversed(stack))))
        elif ch == ",":
            cuts.append((i, "".join(reversed(stack))))

    for end, closers in reversed(cuts[-max_attempts:]):
        try:
            result = json.loads(raw_text[:end] + closers)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            return result
    return None


def _make_digest_id(date_end):
    """Generate a digest ID like '2026-W09-fri'."""
    iso_year, week_num, _ = date_end.isocalendar()
    day_name = date_end.strftime("%a").lower()
    return f"{iso_year}-W{week_num:02d}-{day_name}"


def _update_index(output_dir, meta, filename):
    """Add or replace this digest's entry in index.json, atomically.

    A missing or corrupt index.json is rebuilt from the digest files in
    ``output_dir`` instead of crashing the run.

    Args:
        output_dir: Dashboard data directory.
        meta: The digest's ``meta`` dict.
        filename: The digest's file name.
    """
    index_path = os.path.join(output_dir, "index.json")

    index = read_json_file(index_path)
    if not isinstance(index, dict) or not isinstance(index.get("digests"), list):
        if os.path.exists(index_path):
            print(f"  Warning: {index_path} is corrupt; rebuilding from digest files.")
        index = {"last_updated": None, "digests": rebuild_index_from_dir(output_dir)}

    # Remove existing entry with same ID if re-running
    entries = [d for d in index["digests"]
               if isinstance(d, dict) and d.get("id") != meta["id"]]
    entries.append(index_entry_from_meta(meta, filename))

    index["digests"] = sort_index_entries(entries)
    index["last_updated"] = datetime.now().isoformat()

    atomic_write_json(index_path, index)
    print(f"  Updated {index_path}")
