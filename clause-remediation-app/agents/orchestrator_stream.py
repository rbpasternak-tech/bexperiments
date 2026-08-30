"""Streaming orchestrator for the clause remediation workflow.

Generator version that yields structured JSON events for real-time
dashboard rendering via SSE.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_tools import search_documents, list_documents, get_document
from tools.legal_tools import identify_clause, assess_clause, draft_replacement, review_redline
from tools.docx_tools import read_docx_text, apply_replacements, generate_redline


DOCS_DIR = Path(os.environ.get("DOCS_DIR", str(Path.home() / "Dummy docs")))
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def find_docx_path(filename):
    """Locate a .docx file in the docs directory tree."""
    for path in DOCS_DIR.rglob("*.docx"):
        if path.name == filename:
            return path
    return None


def run_remediation_stream(clause_type, old_standard, new_standard, category_filter=None):
    """Execute clause remediation, yielding events for each step.

    Yields:
        Dict events with 'type' and agent-specific data.
    """
    start_time = time.time()

    yield {
        "type": "init",
        "agent": "ORCHESTRATOR",
        "message": "Starting portfolio-wide clause remediation workflow",
        "scenario": {
            "clause_type": clause_type,
            "old_standard": old_standard,
            "new_standard": new_standard,
            "category_filter": category_filter,
        },
    }

    # --- Phase 1: Search ---
    yield {"type": "phase", "phase": "search", "message": f"Searching portfolio for '{clause_type}' references..."}

    search_results = search_documents(clause_type)
    yield {
        "type": "step",
        "agent": "SEARCH",
        "message": f"Full-text search returned {len(search_results)} documents",
    }

    if category_filter:
        category_docs = list_documents(category=category_filter)
        yield {
            "type": "step",
            "agent": "SEARCH",
            "message": f"Category '{category_filter}' returned {len(category_docs)} documents",
        }
        search_ids = {r["id"] for r in search_results}
        category_ids = {d["id"] for d in category_docs}
        combined_ids = search_ids | category_ids
    else:
        combined_ids = {r["id"] for r in search_results}

    yield {
        "type": "search_complete",
        "agent": "SEARCH",
        "fts_count": len(search_results),
        "combined_count": len(combined_ids),
        "message": f"Combined {len(combined_ids)} unique documents to analyze",
    }

    # --- Phase 2: Analyze ---
    yield {"type": "phase", "phase": "analyze", "message": f"Analyzing {len(combined_ids)} documents for {clause_type} clauses..."}

    documents_analyzed = []
    documents_needing_update = []

    for i, doc_id in enumerate(combined_ids):
        doc = get_document(doc_id)

        yield {
            "type": "doc_analyze_start",
            "agent": "LEGAL",
            "doc_id": doc_id,
            "title": doc["title"],
            "filename": doc.get("filename", ""),
            "category": doc.get("category", ""),
            "progress": f"{i + 1}/{len(combined_ids)}",
            "message": f"Analyzing: {doc['title']}",
        }

        clause_result = identify_clause(doc["body_text"], clause_type)

        if not clause_result.get("found"):
            documents_analyzed.append({
                "id": doc_id,
                "title": doc["title"],
                "filename": doc["filename"],
            })
            yield {
                "type": "doc_analyze_result",
                "agent": "LEGAL",
                "doc_id": doc_id,
                "title": doc["title"],
                "status": "no_clause",
                "confidence": clause_result.get("confidence", 0),
                "message": f"No {clause_type} clause found (confidence: {clause_result.get('confidence', 0):.0%})",
            }
            continue

        assessment = assess_clause(clause_result["clause_text"], new_standard)
        needs_update = assessment.get("needs_update", False)

        doc_record = {
            "id": doc_id,
            "title": doc["title"],
            "filename": doc["filename"],
            "clause_found": True,
            "section": clause_result.get("section"),
            "clause_text": clause_result.get("clause_text"),
            "needs_update": needs_update,
            "reason": assessment.get("reason"),
            "risk_level": assessment.get("risk_level"),
        }
        documents_analyzed.append(doc_record)

        if needs_update:
            documents_needing_update.append(doc_record)

        yield {
            "type": "doc_analyze_result",
            "agent": "LEGAL",
            "doc_id": doc_id,
            "title": doc["title"],
            "status": "needs_update" if needs_update else "current",
            "section": clause_result.get("section"),
            "confidence": clause_result.get("confidence", 0),
            "risk_level": assessment.get("risk_level"),
            "reason": assessment.get("reason", ""),
            "message": (
                f"NEEDS UPDATE: {assessment.get('reason', '')} (risk: {assessment.get('risk_level', '?')})"
                if needs_update
                else f"Already current in {clause_result.get('section', 'document')}"
            ),
        }

    yield {
        "type": "step",
        "agent": "LEGAL",
        "message": f"Analysis complete. {len(documents_needing_update)}/{len(documents_analyzed)} documents need updates.",
    }

    if not documents_needing_update:
        yield {
            "type": "complete",
            "results": {
                "searched": len(combined_ids),
                "analyzed": len(documents_analyzed),
                "needing_update": 0,
                "updated": 0,
                "qa_approved": 0,
                "elapsed_seconds": round(time.time() - start_time, 1),
            },
        }
        return

    # --- Phase 3: Draft ---
    yield {"type": "phase", "phase": "draft", "message": f"Drafting replacement language for {len(documents_needing_update)} documents..."}

    drafts = []
    for doc_record in documents_needing_update:
        yield {
            "type": "doc_draft_start",
            "agent": "LEGAL",
            "doc_id": doc_record["id"],
            "title": doc_record["title"],
            "message": f"Drafting for: {doc_record['title']}",
        }

        draft = draft_replacement(
            original_clause=doc_record["clause_text"],
            target_standard=new_standard,
            context=f"{doc_record['title']} - {clause_type} clause in {doc_record.get('section', 'document')}",
        )
        doc_record["draft"] = draft
        drafts.append(doc_record)

        yield {
            "type": "doc_draft_result",
            "agent": "LEGAL",
            "doc_id": doc_record["id"],
            "title": doc_record["title"],
            "changes_summary": draft.get("changes_summary", "N/A"),
            "message": f"Draft ready: {draft.get('changes_summary', 'N/A')}",
        }

    # --- Phase 4: Process ---
    yield {"type": "phase", "phase": "process", "message": "Applying changes to .docx files..."}

    clean_dir = OUTPUT_DIR / "clean"
    redline_dir = OUTPUT_DIR / "redlines"
    clean_dir.mkdir(parents=True, exist_ok=True)
    redline_dir.mkdir(parents=True, exist_ok=True)

    updated_docs = []
    for doc_record in drafts:
        docx_path = find_docx_path(doc_record["filename"])
        if not docx_path:
            yield {
                "type": "doc_process_result",
                "agent": "PROCESSING",
                "doc_id": doc_record["id"],
                "title": doc_record["title"],
                "status": "skipped",
                "message": f"SKIP: {doc_record['filename']} not found locally",
            }
            continue

        find_text = doc_record["draft"].get("find", "")
        replace_text = doc_record["draft"].get("replace", "")
        if not find_text or not replace_text:
            yield {
                "type": "doc_process_result",
                "agent": "PROCESSING",
                "doc_id": doc_record["id"],
                "title": doc_record["title"],
                "status": "skipped",
                "message": f"SKIP: No find/replace pair in draft",
            }
            continue

        replacements = [{"find": find_text, "replace": replace_text}]

        clean_path = clean_dir / doc_record["filename"]
        clean_result = apply_replacements(docx_path, replacements, clean_path)

        redline_path = redline_dir / doc_record["filename"]
        redline_result = generate_redline(docx_path, replacements, redline_path)

        doc_record["clean_path"] = str(clean_path)
        doc_record["redline_path"] = str(redline_path)
        doc_record["changes_applied"] = clean_result["change_count"]
        updated_docs.append(doc_record)

        yield {
            "type": "doc_process_result",
            "agent": "PROCESSING",
            "doc_id": doc_record["id"],
            "title": doc_record["title"],
            "status": "processed",
            "clean_changes": clean_result["change_count"],
            "redline_changes": redline_result["change_count"],
            "message": f"Applied {clean_result['change_count']} changes + redline",
        }

    # --- Phase 5: QA ---
    yield {"type": "phase", "phase": "qa", "message": f"QA reviewing {len(updated_docs)} updated documents..."}

    qa_results = []
    for doc_record in updated_docs:
        yield {
            "type": "doc_qa_start",
            "agent": "LEGAL",
            "doc_id": doc_record["id"],
            "title": doc_record["title"],
            "message": f"Reviewing: {doc_record['title']}",
        }

        docx_path = find_docx_path(doc_record["filename"])
        original_text = read_docx_text(docx_path) if docx_path else ""
        modified_text = read_docx_text(doc_record["clean_path"]) if doc_record.get("clean_path") else ""

        find_text = doc_record.get("draft", {}).get("find", "")
        if find_text and find_text in original_text:
            idx = original_text.index(find_text)
            start = max(0, idx - 500)
            end = min(len(original_text), idx + len(find_text) + 500)
            original_excerpt = original_text[start:end]
        else:
            original_excerpt = original_text[:4000]

        replace_text = doc_record.get("draft", {}).get("replace", "")
        if replace_text and replace_text in modified_text:
            idx = modified_text.index(replace_text)
            start = max(0, idx - 500)
            end = min(len(modified_text), idx + len(replace_text) + 500)
            modified_excerpt = modified_text[start:end]
        else:
            modified_excerpt = modified_text[:4000]

        review = review_redline(
            original_text=original_excerpt,
            modified_text=modified_excerpt,
            intended_changes=f"Update {clause_type} clause from {old_standard} to {new_standard}",
        )

        doc_record["qa"] = review
        qa_results.append(doc_record)
        approved = review.get("approved", False)

        yield {
            "type": "doc_qa_result",
            "agent": "LEGAL",
            "doc_id": doc_record["id"],
            "title": doc_record["title"],
            "approved": approved,
            "notes": review.get("notes", ""),
            "issues": review.get("issues", []),
            "message": f"{'APPROVED' if approved else 'FLAGGED'}: {review.get('notes', '')}",
        }

    # --- Complete ---
    elapsed = round(time.time() - start_time, 1)
    approved_count = sum(1 for d in qa_results if d.get("qa", {}).get("approved"))

    yield {
        "type": "complete",
        "results": {
            "searched": len(combined_ids),
            "analyzed": len(documents_analyzed),
            "clauses_found": sum(1 for d in documents_analyzed if d.get("clause_found")),
            "needing_update": len(documents_needing_update),
            "updated": len(updated_docs),
            "qa_approved": approved_count,
            "qa_total": len(qa_results),
            "elapsed_seconds": elapsed,
        },
    }
