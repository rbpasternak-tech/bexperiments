"""Supabase query wrappers for the Search Agent.

Provides search, list, get, and stats functions against the
legal-doc-catalog documents table.
"""

import os
from supabase import create_client


def _get_client():
    """Create and authenticate a Supabase client.

    Returns:
        Tuple of (client, user_id).

    Raises:
        RuntimeError: If required env vars are missing.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    email = os.environ.get("SEED_EMAIL")
    password = os.environ.get("SEED_PASSWORD")

    if not all([url, key, email, password]):
        raise RuntimeError(
            "Missing env vars. Set SUPABASE_URL, SUPABASE_SERVICE_KEY or "
            "SUPABASE_ANON_KEY, SEED_EMAIL, SEED_PASSWORD"
        )

    client = create_client(url, key)
    auth = client.auth.sign_in_with_password({"email": email, "password": password})
    return client, auth.user.id


_client = None
_user_id = None


def _ensure_client():
    """Lazy-initialize the Supabase client singleton."""
    global _client, _user_id
    if _client is None:
        _client, _user_id = _get_client()
    return _client


def search_documents(query):
    """Full-text search with highlighted snippets.

    Args:
        query: Search string (supports websearch syntax).

    Returns:
        List of dicts with id, title, category, year, word_count, headline.
    """
    client = _ensure_client()
    result = client.rpc("search_documents", {"search_query": query}).execute()
    return result.data


def list_documents(category=None, year=None):
    """List documents with optional filters.

    Args:
        category: Filter by category name (exact match).
        year: Filter by year (int) or None for undated.

    Returns:
        List of dicts with id, title, category, year, word_count.
    """
    client = _ensure_client()
    q = client.table("documents").select("id, title, filename, category, year, word_count")

    if category:
        q = q.eq("category", category)
    if year is not None:
        q = q.eq("year", year)

    result = q.order("title").execute()
    return result.data


def get_document(doc_id):
    """Retrieve full document record by ID.

    Args:
        doc_id: UUID string of the document.

    Returns:
        Dict with all document fields including body_text.
    """
    client = _ensure_client()
    result = (
        client.table("documents")
        .select("*")
        .eq("id", doc_id)
        .single()
        .execute()
    )
    return result.data


def get_document_stats():
    """Get aggregate counts by category.

    Returns:
        Dict mapping category name to document count.
    """
    client = _ensure_client()
    result = (
        client.table("documents")
        .select("category")
        .execute()
    )
    stats = {}
    for row in result.data:
        cat = row["category"]
        stats[cat] = stats.get(cat, 0) + 1
    return stats
