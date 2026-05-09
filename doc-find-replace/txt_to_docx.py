"""Batch convert .txt files to .docx, deleting .txt after each folder."""

import re
import sys
from pathlib import Path
from docx import Document

_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def clean_text(text):
    return _CONTROL_RE.sub('', text)


def convert_txt_to_docx(txt_path, docx_path):
    doc = Document()
    with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            doc.add_paragraph(clean_text(line.rstrip('\n')))
    doc.save(docx_path)


def process_years(base_dir, years):
    base = Path(base_dir)
    for year in years:
        year_dir = base / str(year)
        txt_files = sorted(year_dir.glob('*.txt'))
        if not txt_files:
            print(f"{year}: no .txt files, skipping")
            continue

        total = len(txt_files)
        print(f"--- {year}: converting {total} files ---")

        for i, txt_file in enumerate(txt_files, 1):
            docx_path = year_dir / (txt_file.stem + '.docx')
            convert_txt_to_docx(txt_file, docx_path)
            if i % 500 == 0:
                print(f"  {i}/{total}")

        print(f"  {total}/{total} converted")

        for txt_file in txt_files:
            txt_file.unlink()
        print(f"  deleted {total} .txt files\n")


if __name__ == '__main__':
    process_years(sys.argv[1], range(2014, 2020))
