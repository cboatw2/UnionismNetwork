#!/usr/bin/env python3
"""Build a human-review template for SCC attendance OCR rows.

Reads rows from scc_students_staging and writes a CSV template with review
columns used by import_scc_reviewed.py.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "unionism.db"
DEFAULT_OUT = ROOT / "data" / "staging" / "scc_ocr" / "scc_students_review_template.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SCC OCR review template CSV")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to unionism.db")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Path to output template CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            staging_id,
            source_file,
            page_number,
            line_number,
            parsed_name,
            parsed_date_text,
            parsed_year,
            ocr_confidence,
            raw_line,
            review_status
        FROM scc_students_staging
        ORDER BY page_number, line_number, staging_id
        """
    ).fetchall()
    conn.close()

    fieldnames = [
        "staging_id",
        "source_file",
        "page_number",
        "line_number",
        "parsed_name",
        "parsed_date_text",
        "parsed_year",
        "ocr_confidence",
        "raw_line",
        "review_status",
        "reviewed_full_name",
        "reviewed_start_year",
        "reviewed_end_year",
        "reviewer_notes",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "staging_id": row["staging_id"],
                    "source_file": row["source_file"],
                    "page_number": row["page_number"],
                    "line_number": row["line_number"],
                    "parsed_name": row["parsed_name"],
                    "parsed_date_text": row["parsed_date_text"],
                    "parsed_year": row["parsed_year"],
                    "ocr_confidence": row["ocr_confidence"],
                    "raw_line": row["raw_line"],
                    "review_status": row["review_status"] or "needs_review",
                    "reviewed_full_name": "",
                    "reviewed_start_year": "",
                    "reviewed_end_year": "",
                    "reviewer_notes": "",
                }
            )

    print(f"Wrote template: {out_path}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
