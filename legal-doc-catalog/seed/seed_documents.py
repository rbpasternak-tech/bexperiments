"""Seed script for Legal Doc Catalog.

Walks a directory of .docx files organized as Category/Year/*.docx,
extracts text via python-docx, and uploads metadata + content to Supabase.
"""

import os
import re
import sys
from pathlib import Path

from docx import Document
from dotenv import load_dotenv
from supabase import create_client


def extract_text(docx_path):
    """Extract all paragraph text from a .docx file.

    Args:
        docx_path: Path to the .docx file.

    Returns:
        Full text as a single string with paragraphs separated by newlines.
    """
    doc = Document(docx_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def humanize_category(folder_name):
    """Convert folder name to display-friendly category.

    Args:
        folder_name: Raw folder name like 'M_and_A_and_Equity'.

    Returns:
        Humanized string like 'M&A & Equity'.
    """
    return folder_name.replace("_and_", " & ").replace("_", " ")


def format_title(filename):
    """Derive a clean title from a .docx filename.

    Args:
        filename: Filename like 'Settlement_Agreement_2019.docx'.

    Returns:
        Title like 'Settlement Agreement'.
    """
    name = re.sub(r"\.docx$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"_(\d{4})$", "", name)
    return name.replace("_", " ")


def parse_year(subfolder):
    """Parse year from subfolder name.

    Args:
        subfolder: Subfolder name like '2019' or 'undated'.

    Returns:
        Integer year or None for undated documents.
    """
    if subfolder == "undated":
        return None
    try:
        return int(subfolder)
    except ValueError:
        return None


def collect_documents(base_dir):
    """Walk directory tree and collect document metadata.

    Args:
        base_dir: Path to the root documents directory.

    Returns:
        List of dicts with keys: filename, title, category, year, body_text, word_count.
    """
    documents = []
    base = Path(base_dir)

    for category_dir in sorted(base.iterdir()):
        if not category_dir.is_dir() or category_dir.name.startswith("."):
            continue

        category = humanize_category(category_dir.name)

        for year_dir in sorted(category_dir.iterdir()):
            if not year_dir.is_dir() or year_dir.name.startswith("."):
                continue

            year = parse_year(year_dir.name)

            for docx_file in sorted(year_dir.glob("*.docx")):
                title = format_title(docx_file.name)
                body_text = extract_text(docx_file)
                word_count = len(body_text.split())

                documents.append({
                    "filename": docx_file.name,
                    "title": title,
                    "category": category,
                    "year": year,
                    "body_text": body_text,
                    "word_count": word_count,
                })

    return documents


def seed(supabase_client, user_id, documents):
    """Upload documents to Supabase, skipping duplicates.

    Args:
        supabase_client: Authenticated Supabase client.
        user_id: UUID of the authenticated user.
        documents: List of document dicts from collect_documents.

    Returns:
        Tuple of (inserted_count, skipped_count).
    """
    existing = supabase_client.table("documents").select("filename").execute()
    existing_filenames = {row["filename"] for row in existing.data}

    inserted = 0
    skipped = 0

    for doc in documents:
        if doc["filename"] in existing_filenames:
            print(f"  Skip (exists): {doc['filename']}")
            skipped += 1
            continue

        row = {
            "user_id": user_id,
            "filename": doc["filename"],
            "title": doc["title"],
            "category": doc["category"],
            "year": doc["year"],
            "body_text": doc["body_text"],
            "word_count": doc["word_count"],
        }
        supabase_client.table("documents").insert(row).execute()
        print(f"  Inserted: {doc['filename']}")
        inserted += 1

    return inserted, skipped


def main():
    """Run the seed script."""
    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    email = os.environ.get("SEED_EMAIL")
    password = os.environ.get("SEED_PASSWORD")
    base_dir = os.environ.get("DOCS_DIR", str(Path.home() / "Dummy docs"))

    if not all([url, key, email, password]):
        print("Missing required environment variables.")
        print("Set: SUPABASE_URL, SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY),")
        print("     SEED_EMAIL, SEED_PASSWORD")
        print("Optionally: DOCS_DIR (defaults to ~/Dummy docs)")
        sys.exit(1)

    print(f"Connecting to Supabase: {url}")
    client = create_client(url, key)

    print(f"Signing in as {email}...")
    auth_response = client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })
    user_id = auth_response.user.id
    print(f"Authenticated. User ID: {user_id}")

    print(f"Scanning documents in: {base_dir}")
    documents = collect_documents(base_dir)
    print(f"Found {len(documents)} documents.")

    print("Seeding to Supabase...")
    inserted, skipped = seed(client, user_id, documents)
    print(f"Done. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
