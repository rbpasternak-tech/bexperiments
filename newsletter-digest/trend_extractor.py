"""Extract structured trend data from digest content for the dashboard."""

import json
import os
from datetime import datetime

import anthropic

from email_parser import extract_text

EXTRACTION_PROMPT = """\
You are a structured data extraction system. You will receive tech and legal tech newsletter content and RSS articles. Extract structured data for a trends dashboard.

Return ONLY valid JSON matching the schema below. No text before or after the JSON.

Extract:

1. **topics**: Distinct topics across all sources. Each:
   - "name": Short label (2-5 words, e.g., "AI Agents", "EU AI Act")
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
    content_parts = _build_content(newsletters, rss_articles)

    if not content_parts:
        print("  No content to extract trends from.")
        return

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": "Extract structured data:\n\n" + "\n".join(content_parts)}],
    )

    raw_text = response.content[0].text.strip()
    # Handle potential markdown code fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()

    extracted = json.loads(raw_text)

    # Build digest ID from date
    digest_id = _make_digest_id(date_end)
    source_names = list(set(
        [a.source for a in rss_articles]
        + [e.get("sender", "").split("<")[0].strip() for e in newsletters if e.get("sender")]
    ))

    output = {
        "meta": {
            "id": digest_id,
            "run_date": datetime.now().isoformat(),
            "date_range_start": date_start.strftime("%Y-%m-%d"),
            "date_range_end": date_end.strftime("%Y-%m-%d"),
            "newsletter_count": len(newsletters),
            "rss_article_count": len(rss_articles),
            "sources_analyzed": source_names,
        },
        **extracted,
    }

    # Write per-digest file
    os.makedirs(output_dir, exist_ok=True)
    filename = f"digest-{digest_id}.json"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Wrote {filepath}")

    # Update index.json
    _update_index(output_dir, output["meta"], filename)


def _build_content(newsletters, rss_articles):
    """Build content string from newsletters and RSS articles."""
    parts = []

    if newsletters:
        parts.append("=== NEWSLETTER EMAILS ===\n")
        for i, email in enumerate(newsletters, 1):
            text = extract_text(email)
            if not text.strip():
                continue
            parts.append(
                f"--- Newsletter {i} ---\n"
                f"From: {email.get('sender', 'Unknown')}\n"
                f"Subject: {email.get('subject', 'No subject')}\n"
                f"Date: {email.get('date', '')}\n\n"
                f"{text}\n"
            )

    if rss_articles:
        parts.append("\n=== RSS FEED ARTICLES ===\n")
        for article in rss_articles:
            parts.append(
                f"--- {article.source} ---\n"
                f"Title: {article.title}\n"
                f"URL: {article.url}\n"
                f"Date: {article.published.strftime('%Y-%m-%d')}\n"
                f"Summary: {article.summary}\n"
            )

    return parts


def _make_digest_id(date_end):
    """Generate a digest ID like '2026-W09-fri'."""
    week_num = date_end.isocalendar()[1]
    day_name = date_end.strftime("%a").lower()
    return f"{date_end.year}-W{week_num:02d}-{day_name}"


def _update_index(output_dir, meta, filename):
    """Update or create index.json with the new digest entry."""
    index_path = os.path.join(output_dir, "index.json")

    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            index = json.load(f)
    else:
        index = {"last_updated": None, "digests": []}

    # Remove existing entry with same ID if re-running
    index["digests"] = [d for d in index["digests"] if d.get("id") != meta["id"]]

    index["digests"].append({
        "id": meta["id"],
        "run_date": meta["date_range_end"],
        "date_range_start": meta["date_range_start"],
        "date_range_end": meta["date_range_end"],
        "file": filename,
        "newsletter_count": meta["newsletter_count"],
        "rss_article_count": meta["rss_article_count"],
    })

    # Sort by run date
    index["digests"].sort(key=lambda d: d["run_date"])
    index["last_updated"] = datetime.now().isoformat()

    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"  Updated {index_path}")
