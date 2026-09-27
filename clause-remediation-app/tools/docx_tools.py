"""Document processing tools for the Processing Agent.

Python port of doc-find-replace JS logic using python-docx.
Handles find/replace, redline generation, and term extraction.
"""

import copy
import re
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph
from lxml import etree

NSMAP = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _iter_container_paragraphs(container, parent):
    """Yield paragraphs in document order from a body or table cell element.

    Descends into tables (including nested tables) so that paragraphs
    inside table cells are included. Each w:tc element is visited once,
    so merged cells are not processed twice.

    Args:
        container: lxml element (w:body or w:tc) holding block content.
        parent: python-docx parent object for the Paragraph proxies.

    Yields:
        docx.text.paragraph.Paragraph objects.
    """
    for child in container.iterchildren():
        if child.tag == f"{W}p":
            yield Paragraph(child, parent)
        elif child.tag == f"{W}tbl":
            for row in child.iterchildren(f"{W}tr"):
                for cell in row.iterchildren(f"{W}tc"):
                    yield from _iter_container_paragraphs(cell, parent)


def iter_all_paragraphs(doc):
    """Yield every body paragraph, including those inside table cells.

    Args:
        doc: A python-docx Document.

    Yields:
        docx.text.paragraph.Paragraph objects in document order.
    """
    yield from _iter_container_paragraphs(doc.element.body, doc)


def read_docx_text(docx_path):
    """Extract all paragraph text (body and tables) from a .docx file.

    Args:
        docx_path: Path to the .docx file.

    Returns:
        Full text with paragraphs separated by newlines.
    """
    doc = Document(docx_path)
    return "\n".join(p.text for p in iter_all_paragraphs(doc) if p.text.strip())


def build_docx_index(docs_dir):
    """Index .docx files under a directory by filename.

    Scans the tree once so that per-document lookups are O(1). If the same
    filename appears in several folders, the first path in sorted order wins.

    Args:
        docs_dir: Root directory to scan (a missing directory yields {}).

    Returns:
        Dict mapping filename to Path.
    """
    index = {}
    for path in sorted(Path(docs_dir).rglob("*.docx")):
        index.setdefault(path.name, path)
    return index


def _detect_case(text):
    """Detect the case pattern of a string.

    Args:
        text: The string to analyze.

    Returns:
        One of 'upper', 'lower', 'title', 'capitalized', 'mixed'.
    """
    if text == text.upper() and text != text.lower():
        return "upper"
    if text == text.lower():
        return "lower"
    words = text.split()
    if len(words) > 1 and all(w[0].isupper() for w in words if w):
        return "title"
    if text[0].isupper() and text[1:] == text[1:].lower():
        return "capitalized"
    return "mixed"


def _apply_case(replacement, case_type):
    """Apply a case pattern to replacement text.

    Args:
        replacement: The replacement string.
        case_type: One of 'upper', 'lower', 'title', 'capitalized', 'mixed'.

    Returns:
        Case-adjusted replacement string.
    """
    if case_type == "upper":
        return replacement.upper()
    if case_type == "lower":
        return replacement.lower()
    if case_type == "title":
        return replacement.title()
    if case_type == "capitalized":
        return replacement[:1].upper() + replacement[1:]
    return replacement


def apply_replacements(docx_path, replacements, output_path):
    """Apply find/replace pairs to a .docx file (clean version).

    Args:
        docx_path: Path to the source .docx file.
        replacements: List of dicts with 'find' and 'replace' keys.
        output_path: Path to write the modified .docx.

    Returns:
        Dict with 'output_path' and 'change_count'.
    """
    doc = Document(docx_path)
    total_changes = 0
    patterns = [
        (re.compile(re.escape(r["find"]), re.IGNORECASE), r["replace"])
        for r in replacements
        if r.get("find")
    ]

    for para in iter_all_paragraphs(doc):
        full_text = para.text
        modified = full_text
        para_changes = 0

        for pattern, replace_text in patterns:
            def _replacer(m, replace_text=replace_text):
                return _apply_case(replace_text, _detect_case(m.group(0)))
            modified, count = pattern.subn(_replacer, modified)
            para_changes += count

        if modified != full_text:
            total_changes += para_changes

            # Collapses the paragraph's text into its first run; formatting
            # of later runs is lost (not a run-aware rewrite).
            runs = para.runs
            if runs:
                runs[0].text = modified
                for run in runs[1:]:
                    run.text = ""

    doc.save(output_path)
    return {"output_path": str(output_path), "change_count": total_changes}


def generate_redline(docx_path, replacements, output_path):
    """Create a tracked-changes version of a .docx file.

    Uses w:del and w:ins XML elements to mark deletions and insertions,
    matching the JS redline logic from doc-find-replace.

    Args:
        docx_path: Path to the source .docx file.
        replacements: List of dicts with 'find' and 'replace' keys.
        output_path: Path to write the redlined .docx.

    Returns:
        Dict with 'output_path' and 'change_count'.
    """
    doc = Document(docx_path)
    change_id = 100
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    author = "Clause Remediation App"
    total_changes = 0

    for para in iter_all_paragraphs(doc):
        full_text = para.text
        if not full_text.strip():
            continue

        candidates = []
        for r in replacements:
            if not r.get("find"):
                continue
            for m in re.finditer(re.escape(r["find"]), full_text, re.IGNORECASE):
                case_type = _detect_case(m.group(0))
                candidates.append({
                    "start": m.start(),
                    "end": m.end(),
                    "original": m.group(0),
                    "replacement": _apply_case(r["replace"], case_type),
                })

        # Earliest match wins; at the same start the longer match wins.
        # Matches overlapping an already-accepted match are skipped so the
        # same text is never deleted twice.
        candidates.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
        all_matches = []
        last_end = 0
        for match in candidates:
            if match["start"] >= last_end:
                all_matches.append(match)
                last_end = match["end"]

        if not all_matches:
            continue

        total_changes += len(all_matches)

        rpr_source = None
        for run in para.runs:
            rpr_el = run._element.find(f"{W}rPr")
            if rpr_el is not None:
                rpr_source = copy.deepcopy(rpr_el)
                break

        p_element = para._element
        for run in list(para.runs):
            p_element.remove(run._element)

        cursor = 0
        for match in all_matches:
            if cursor < match["start"]:
                _add_run(p_element, full_text[cursor:match["start"]], rpr_source)

            del_el = etree.SubElement(p_element, f"{W}del")
            del_el.set(f"{W}id", str(change_id))
            del_el.set(f"{W}author", author)
            del_el.set(f"{W}date", date_str)
            change_id += 1

            del_run = etree.SubElement(del_el, f"{W}r")
            if rpr_source is not None:
                del_run.append(copy.deepcopy(rpr_source))
            del_text = etree.SubElement(del_run, f"{W}delText")
            del_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            del_text.text = match["original"]

            ins_el = etree.SubElement(p_element, f"{W}ins")
            ins_el.set(f"{W}id", str(change_id))
            ins_el.set(f"{W}author", author)
            ins_el.set(f"{W}date", date_str)
            change_id += 1

            ins_run = etree.SubElement(ins_el, f"{W}r")
            if rpr_source is not None:
                ins_run.append(copy.deepcopy(rpr_source))
            ins_text = etree.SubElement(ins_run, f"{W}t")
            ins_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            ins_text.text = match["replacement"]

            cursor = match["end"]

        if cursor < len(full_text):
            _add_run(p_element, full_text[cursor:], rpr_source)

    doc.save(output_path)
    return {"output_path": str(output_path), "change_count": total_changes}


def _add_run(p_element, text, rpr_source):
    """Add a plain text run to a paragraph element.

    Args:
        p_element: The w:p lxml element.
        text: Text content for the run.
        rpr_source: Optional run properties element to clone.
    """
    run = etree.SubElement(p_element, f"{W}r")
    if rpr_source is not None:
        run.append(copy.deepcopy(rpr_source))
    t = etree.SubElement(run, f"{W}t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text


def extract_defined_terms(docx_path):
    """Extract defined terms from a legal document.

    Finds bracketed [terms], quoted "Terms", and capitalized Defined Terms.

    Args:
        docx_path: Path to the .docx file.

    Returns:
        List of dicts with 'term', 'type', and 'count' keys.
    """
    text = read_docx_text(docx_path)
    results = []
    seen = set()

    for m in re.finditer(r'\[([a-zA-Z0-9][a-zA-Z0-9 -]*[a-zA-Z0-9])\]', text):
        key = m.group(1).lower()
        if key not in seen:
            seen.add(key)
            count = len(re.findall(re.escape(m.group(0)), text, re.IGNORECASE))
            results.append({"term": m.group(1), "type": "bracket", "count": count})

    for m in re.finditer(r'["“”]([A-Z][^"“”\n]{0,79})["“”]', text):
        term = m.group(1).strip()
        key = term.lower()
        if key not in seen and len(term) >= 2:
            seen.add(key)
            count = len(re.findall(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE))
            results.append({"term": term, "type": "quoted", "count": count})

    cap_pattern = re.compile(
        r'\b([A-Z][a-z]+(?:-[A-Z][a-z]+)*'
        r'(?:\s+(?:of|the|and|or|for|in|on|to|by|a|an|at|as|with|from)'
        r'\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)*'
        r'|\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)*)+)\b'
    )
    cap_counts = {}
    for m in cap_pattern.finditer(text):
        phrase = re.sub(r'^(?:The|A|An)\s+', '', m.group(1))
        key = phrase.lower()
        if key in seen:
            continue
        cap_counts[key] = cap_counts.get(key, {"phrase": phrase, "count": 0})
        cap_counts[key]["count"] += 1

    for key, info in cap_counts.items():
        if info["count"] >= 2:
            seen.add(key)
            results.append({"term": info["phrase"], "type": "defined", "count": info["count"]})

    return results
