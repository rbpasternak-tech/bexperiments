"""Orchestrator for the clause remediation workflow.

Coordinates Search, Legal, and Processing agents to execute
portfolio-wide clause updates with full narration.
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


def narrate(step, message):
    """Print a narrated step with formatting.

    Args:
        step: Step label (e.g., 'SEARCH', 'LEGAL', 'PROCESSING').
        message: Description of what's happening.
    """
    colors = {
        "ORCHESTRATOR": "\033[1;35m",
        "SEARCH": "\033[1;36m",
        "LEGAL": "\033[1;33m",
        "PROCESSING": "\033[1;32m",
        "RESULT": "\033[1;37m",
    }
    reset = "\033[0m"
    color = colors.get(step, "\033[1;37m")
    print(f"\n{color}[{step}]{reset} {message}")


def find_docx_path(filename):
    """Locate a .docx file in the Dummy docs directory tree.

    Args:
        filename: The filename to search for.

    Returns:
        Path to the file, or None if not found.
    """
    for path in DOCS_DIR.rglob("*.docx"):
        if path.name == filename:
            return path
    return None


def run_remediation(clause_type, old_standard, new_standard, category_filter=None):
    """Execute the full clause remediation workflow.

    Args:
        clause_type: Type of clause to target (e.g., 'arbitration').
        old_standard: Current/outdated reference to find.
        new_standard: Updated reference to replace with.
        category_filter: Optional category to limit search scope.

    Returns:
        Dict with workflow results and statistics.
    """
    start_time = time.time()

    narrate("ORCHESTRATOR", "Starting portfolio-wide clause remediation workflow")
    narrate("ORCHESTRATOR", f"Target: {clause_type} clauses referencing '{old_standard}'")
    narrate("ORCHESTRATOR", f"Update to: '{new_standard}'")
    print()

    # Step 1: Search Agent finds documents
    narrate("SEARCH", f"Searching portfolio for '{clause_type}' references...")
    search_results = search_documents(clause_type)
    narrate("SEARCH", f"Full-text search returned {len(search_results)} documents")

    if category_filter:
        narrate("SEARCH", f"Filtering to category: {category_filter}")
        category_docs = list_documents(category=category_filter)
        narrate("SEARCH", f"Category filter returned {len(category_docs)} documents")

        search_ids = {r["id"] for r in search_results}
        category_ids = {d["id"] for d in category_docs}
        combined_ids = search_ids | category_ids
        narrate("SEARCH", f"Combined unique documents to analyze: {len(combined_ids)}")
    else:
        combined_ids = {r["id"] for r in search_results}

    # Step 2: Legal Agent analyzes each document
    narrate("LEGAL", f"Analyzing {len(combined_ids)} documents for {clause_type} clauses...")
    documents_analyzed = []
    documents_needing_update = []

    for doc_id in combined_ids:
        doc = get_document(doc_id)
        narrate("LEGAL", f"  Analyzing: {doc['title']}")

        clause_result = identify_clause(doc["body_text"], clause_type)

        if not clause_result.get("found"):
            narrate("LEGAL", f"    No {clause_type} clause found (confidence: {clause_result.get('confidence', 0):.0%})")
            documents_analyzed.append({
                "id": doc_id,
                "title": doc["title"],
                "filename": doc["filename"],
                "clause_found": False,
            })
            continue

        narrate("LEGAL", f"    Found in {clause_result.get('section', 'unknown section')} "
                f"(confidence: {clause_result.get('confidence', 0):.0%})")

        assessment = assess_clause(clause_result["clause_text"], new_standard)

        doc_record = {
            "id": doc_id,
            "title": doc["title"],
            "filename": doc["filename"],
            "clause_found": True,
            "section": clause_result.get("section"),
            "clause_text": clause_result.get("clause_text"),
            "needs_update": assessment.get("needs_update", False),
            "reason": assessment.get("reason"),
            "risk_level": assessment.get("risk_level"),
        }
        documents_analyzed.append(doc_record)

        if assessment.get("needs_update"):
            narrate("LEGAL", f"    NEEDS UPDATE: {assessment.get('reason')} "
                    f"(risk: {assessment.get('risk_level', 'unknown')})")
            documents_needing_update.append(doc_record)
        else:
            narrate("LEGAL", f"    Already current - no update needed")

    narrate("LEGAL", f"Analysis complete. {len(documents_needing_update)} documents need updates.")

    if not documents_needing_update:
        narrate("ORCHESTRATOR", "No documents require updates. Workflow complete.")
        return {
            "searched": len(combined_ids),
            "analyzed": len(documents_analyzed),
            "needing_update": 0,
            "updated": 0,
            "documents": documents_analyzed,
            "elapsed_seconds": time.time() - start_time,
        }

    # Step 3: Legal Agent drafts replacements
    narrate("LEGAL", "Drafting replacement language for each document...")
    drafts = []
    for doc_record in documents_needing_update:
        narrate("LEGAL", f"  Drafting for: {doc_record['title']}")
        draft = draft_replacement(
            original_clause=doc_record["clause_text"],
            target_standard=new_standard,
            context=f"{doc_record['title']} - {clause_type} clause in {doc_record.get('section', 'document')}",
        )
        narrate("LEGAL", f"    Changes: {draft.get('changes_summary', 'N/A')}")
        doc_record["draft"] = draft
        drafts.append(doc_record)

    # Step 4: Processing Agent applies changes
    narrate("PROCESSING", "Applying changes to .docx files...")
    updated_docs = []

    clean_dir = OUTPUT_DIR / "clean"
    redline_dir = OUTPUT_DIR / "redlines"
    clean_dir.mkdir(parents=True, exist_ok=True)
    redline_dir.mkdir(parents=True, exist_ok=True)

    for doc_record in drafts:
        docx_path = find_docx_path(doc_record["filename"])
        if not docx_path:
            narrate("PROCESSING", f"  SKIP: {doc_record['filename']} not found locally")
            continue

        narrate("PROCESSING", f"  Processing: {doc_record['filename']}")

        find_text = doc_record["draft"].get("find", "")
        replace_text = doc_record["draft"].get("replace", "")
        if not find_text or not replace_text:
            narrate("PROCESSING", f"    SKIP: No find/replace pair in draft")
            continue

        replacements = [{"find": find_text, "replace": replace_text}]

        clean_path = clean_dir / doc_record["filename"]
        clean_result = apply_replacements(docx_path, replacements, clean_path)
        narrate("PROCESSING", f"    Clean version: {clean_result['change_count']} changes")

        redline_path = redline_dir / doc_record["filename"]
        redline_result = generate_redline(docx_path, replacements, redline_path)
        narrate("PROCESSING", f"    Redline version: {redline_result['change_count']} tracked changes")

        doc_record["clean_path"] = str(clean_path)
        doc_record["redline_path"] = str(redline_path)
        doc_record["changes_applied"] = clean_result["change_count"]
        updated_docs.append(doc_record)

    # Step 5: Legal Agent QAs the changes
    narrate("LEGAL", "QA reviewing changes...")
    qa_results = []
    for doc_record in updated_docs:
        narrate("LEGAL", f"  Reviewing: {doc_record['title']}")

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

        status = "APPROVED" if review.get("approved") else "FLAGGED"
        narrate("LEGAL", f"    {status}: {review.get('notes', 'No notes')}")
        doc_record["qa"] = review
        qa_results.append(doc_record)

    # Final report
    elapsed = time.time() - start_time
    approved_count = sum(1 for d in qa_results if d.get("qa", {}).get("approved"))

    narrate("ORCHESTRATOR", "=" * 60)
    narrate("RESULT", "REMEDIATION COMPLETE")
    print(f"""
    Searched:        {len(combined_ids)} documents in portfolio
    Analyzed:        {len(documents_analyzed)} documents for {clause_type} clauses
    Found clause:    {sum(1 for d in documents_analyzed if d.get('clause_found'))} documents
    Needed update:   {len(documents_needing_update)} documents
    Updated:         {len(updated_docs)} documents
    QA approved:     {approved_count}/{len(qa_results)}
    Clean versions:  {clean_dir}/
    Redline versions:{redline_dir}/
    Elapsed:         {elapsed:.1f}s
    """)

    if updated_docs:
        print("    Documents updated:")
        for d in updated_docs:
            section = d.get("section", "unknown")
            changes = d.get("changes_applied", 0)
            qa_status = "pass" if d.get("qa", {}).get("approved") else "FLAG"
            print(f"      {d['filename']} - {section} ({changes} changes) [{qa_status}]")

    return {
        "searched": len(combined_ids),
        "analyzed": len(documents_analyzed),
        "needing_update": len(documents_needing_update),
        "updated": len(updated_docs),
        "qa_approved": approved_count,
        "documents": qa_results,
        "elapsed_seconds": elapsed,
    }
