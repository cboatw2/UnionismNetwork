#!/usr/bin/env python3
"""Import accepted SCC attendance rows from reviewed CSV into unionism.db.

Expected input columns (from build_scc_review_template.py):
- staging_id
- review_status
- reviewed_full_name
- reviewed_start_year
- reviewed_end_year
- parsed_name
- raw_line
- page_number
- reviewer_notes

Only rows with review_status=accepted and reviewed_full_name populated are loaded.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "unionism.db"
DEFAULT_REVIEW_CSV = ROOT / "data" / "staging" / "scc_ocr" / "scc_students_review_template.csv"
PDF_NAME = "South_Carolina_College_Student_List_1806-1835.pdf"
SCC_ORG_NAME = "South Carolina College"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import accepted SCC reviewed rows")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to unionism.db")
    parser.add_argument("--csv", default=str(DEFAULT_REVIEW_CSV), help="Path to reviewed CSV")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    return parser.parse_args()


def clean(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s2 = s.strip()
    return s2 if s2 else None


def parse_year(s: Optional[str]) -> Optional[int]:
    s = clean(s)
    if not s:
        return None
    try:
        y = int(s)
    except ValueError:
        return None
    if 1700 <= y <= 1900:
        return y
    return None


def get_or_create_source(conn: sqlite3.Connection) -> int:
    title = "South Carolina College Attendance Books, 1806-1835"
    row = conn.execute(
        "SELECT source_id FROM sources WHERE title = ? ORDER BY source_id LIMIT 1",
        (title,),
    ).fetchone()
    if row:
        return int(row[0])

    cur = conn.execute(
        """
        INSERT INTO sources (source_type_code, title, archive, collection, url, citation_full, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "primary",
            title,
            "University of South Carolina Archives",
            "South Carolina Collection",
            PDF_NAME,
            "South Carolina College Attendance Books (1806-1835), University of South Carolina Archives.",
            "Imported via reviewed OCR workflow from scanned manuscript ledger pages.",
        ),
    )
    return int(cur.lastrowid)


def get_scc_org_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT organization_id FROM organizations WHERE name = ? ORDER BY organization_id LIMIT 1",
        (SCC_ORG_NAME,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Missing organization: {SCC_ORG_NAME}")
    return int(row[0])


def get_or_create_person(conn: sqlite3.Connection, full_name: str, note: str) -> tuple[int, bool]:
    row = conn.execute(
        "SELECT person_id FROM people WHERE lower(full_name)=lower(?) ORDER BY person_id LIMIT 1",
        (full_name,),
    ).fetchone()
    if row:
        return int(row[0]), False

    cur = conn.execute(
        "INSERT INTO people (full_name, display_name, notes) VALUES (?, ?, ?)",
        (full_name, full_name, note),
    )
    return int(cur.lastrowid), True


def ensure_alias(conn: sqlite3.Connection, person_id: int, alias_name: str, source_id: int, note: str) -> bool:
    row = conn.execute(
        "SELECT alias_id FROM person_aliases WHERE person_id=? AND lower(alias_name)=lower(?)",
        (person_id, alias_name),
    ).fetchone()
    if row:
        return False
    conn.execute(
        "INSERT INTO person_aliases (person_id, alias_name, source_id, notes) VALUES (?, ?, ?, ?)",
        (person_id, alias_name, source_id, note),
    )
    return True


def ensure_attendance(
    conn: sqlite3.Connection,
    person_id: int,
    org_id: int,
    source_id: int,
    start_year: Optional[int],
    end_year: Optional[int],
    note: str,
) -> bool:
    ds = str(start_year) if start_year is not None else None
    de = str(end_year) if end_year is not None else None

    row = conn.execute(
        """
        SELECT person_org_id
        FROM person_organization
        WHERE person_id = ?
          AND organization_id = ?
          AND COALESCE(role, '') = 'Student'
          AND COALESCE(date_start, '') = COALESCE(?, '')
          AND COALESCE(date_end, '') = COALESCE(?, '')
        """,
        (person_id, org_id, ds, de),
    ).fetchone()
    if row:
        return False

    conn.execute(
        """
        INSERT INTO person_organization (person_id, organization_id, role, date_start, date_end, source_id, notes)
        VALUES (?, ?, 'Student', ?, ?, ?, ?)
        """,
        (person_id, org_id, ds, de, source_id, note),
    )
    return True


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)
    csv_path = Path(args.csv)

    if not csv_path.exists():
        raise SystemExit(f"Missing CSV: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")

        source_id = get_or_create_source(conn)
        org_id = get_scc_org_id(conn)

        seen = 0
        accepted = 0
        skipped = 0
        people_created = 0
        aliases_created = 0
        attendance_created = 0

        for row in rows:
            seen += 1
            status = (clean(row.get("review_status")) or "").lower()
            if status != "accepted":
                skipped += 1
                continue

            reviewed_name = clean(row.get("reviewed_full_name"))
            if not reviewed_name:
                skipped += 1
                continue

            accepted += 1

            page_no = clean(row.get("page_number")) or "?"
            raw_line = clean(row.get("raw_line")) or ""
            notes = clean(row.get("reviewer_notes")) or ""

            start_year = parse_year(row.get("reviewed_start_year"))
            end_year = parse_year(row.get("reviewed_end_year"))
            if start_year is not None and end_year is not None and end_year < start_year:
                start_year, end_year = end_year, start_year

            person_note = f"SCC attendance import from reviewed OCR, source page {page_no}."
            person_id, created = get_or_create_person(conn, reviewed_name, person_note)
            if created:
                people_created += 1

            parsed_name = clean(row.get("parsed_name"))
            if parsed_name and parsed_name.lower() != reviewed_name.lower() and len(parsed_name) >= 4:
                alias_note = f"OCR variant from SCC attendance page {page_no}."
                if ensure_alias(conn, person_id, parsed_name, source_id, alias_note):
                    aliases_created += 1

            att_note = f"Imported from {PDF_NAME}; page {page_no}."
            if raw_line:
                att_note += f" OCR line: {raw_line}"
            if notes:
                att_note += f" Reviewer note: {notes}"

            if ensure_attendance(conn, person_id, org_id, source_id, start_year, end_year, att_note):
                attendance_created += 1

            staging_id = clean(row.get("staging_id"))
            if staging_id and staging_id.isdigit():
                conn.execute(
                    "UPDATE scc_students_staging SET review_status = 'accepted' WHERE staging_id = ?",
                    (int(staging_id),),
                )

        if args.dry_run:
            conn.rollback()
            committed = False
        else:
            conn.commit()
            committed = True

        print("Import summary")
        print(f"  rows_seen: {seen}")
        print(f"  accepted_rows_processed: {accepted}")
        print(f"  skipped_rows: {skipped}")
        print(f"  people_created: {people_created}")
        print(f"  aliases_created: {aliases_created}")
        print(f"  attendance_rows_created: {attendance_created}")
        print(f"  source_id_used: {source_id}")
        print(f"  committed: {committed}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
