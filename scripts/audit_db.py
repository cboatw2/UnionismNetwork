from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


ISOISH = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


@dataclass(frozen=True)
class Finding:
    level: str  # INFO | WARN | ERROR
    message: str


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _has_tables(conn: sqlite3.Connection, required: Iterable[str]) -> List[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r[0] for r in rows}
    return sorted(set(required) - names)


def _bad_date_samples(conn: sqlite3.Connection, table: str, col: str, *, limit: int = 10) -> List[str]:
    vals = [r[0] for r in conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL").fetchall()]
    bad = [str(v) for v in vals if not ISOISH.match(str(v))]
    return bad[:limit]


def main() -> None:
    p = argparse.ArgumentParser(description="Audit unionism.db for integrity, FK violations, and common data issues.")
    p.add_argument("--db", default="unionism.db", help="SQLite DB path (relative to repo root)")
    p.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit non-zero if any WARN findings are present.",
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve()

    if not db_path.exists() or db_path.stat().st_size == 0:
        raise SystemExit(f"DB not found or empty: {db_path}")

    findings: List[Finding] = []

    conn = _connect(db_path)
    try:
        required_tables = [
            "people",
            "places",
            "sources",
            "relationships",
            "relationship_characterizations",
            "positions",
            "person_place_residence",
            "lkp_issue_category",
            "lkp_scale_level",
        ]
        missing = _has_tables(conn, required_tables)
        if missing:
            findings.append(Finding("ERROR", f"Missing required tables: {missing}"))

        quick = conn.execute("PRAGMA quick_check;").fetchone()[0]
        if quick != "ok":
            findings.append(Finding("ERROR", f"PRAGMA quick_check returned: {quick}"))
        else:
            findings.append(Finding("INFO", "PRAGMA quick_check: ok"))

        fk_rows = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_rows:
            findings.append(Finding("ERROR", f"Foreign key violations: {len(fk_rows)} (showing up to 10)"))
            for r in fk_rows[:10]:
                findings.append(Finding("ERROR", f"FK violation row: {dict(r)}"))
        else:
            findings.append(Finding("INFO", "PRAGMA foreign_key_check: 0 rows"))

        # Lookup consistency: relationship_type_code values should exist in lookup.
        missing_rel_types = conn.execute(
            """
            SELECT DISTINCT r.relationship_type_code
            FROM relationships r
            LEFT JOIN lkp_relationship_type l ON l.relationship_type_code = r.relationship_type_code
            WHERE l.relationship_type_code IS NULL
            ORDER BY r.relationship_type_code;
            """
        ).fetchall()
        if missing_rel_types:
            findings.append(
                Finding(
                    "WARN",
                    "Relationships contain relationship_type_code values missing from lkp_relationship_type: "
                    + ", ".join([r[0] for r in missing_rel_types]),
                )
            )

        # Basic name hygiene.
        name_stats = conn.execute(
            """
            SELECT
              COUNT(*) AS n,
              SUM(CASE WHEN full_name IS NULL OR trim(full_name) = '' THEN 1 ELSE 0 END) AS missing_full,
              SUM(CASE WHEN display_name IS NULL OR trim(display_name) = '' THEN 1 ELSE 0 END) AS missing_display,
              SUM(CASE WHEN (full_name IS NULL OR trim(full_name) = '') AND (display_name IS NULL OR trim(display_name) = '') THEN 1 ELSE 0 END) AS missing_both
            FROM people;
            """
        ).fetchone()
        if name_stats["missing_both"]:
            findings.append(Finding("WARN", f"People with neither full_name nor display_name: {name_stats['missing_both']}"))

        # Geography completeness.
        missing_geo = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM places
            WHERE latitude IS NULL OR longitude IS NULL;
            """
        ).fetchone()["n"]
        if missing_geo:
            findings.append(Finding("WARN", f"Places missing latitude/longitude: {missing_geo}"))

        # Date format sanity: allow YYYY, YYYY-MM, YYYY-MM-DD.
        date_cols: List[Tuple[str, str]] = [
            ("events", "start_date"),
            ("events", "end_date"),
            ("relationships", "start_date"),
            ("relationships", "end_date"),
            ("relationship_characterizations", "date_start"),
            ("relationship_characterizations", "date_end"),
            ("positions", "date_start"),
            ("positions", "date_end"),
            ("person_place_residence", "date_start"),
            ("person_place_residence", "date_end"),
            ("sources", "date_created"),
            ("correspondence", "date_sent"),
        ]
        for table, col in date_cols:
            bad = _bad_date_samples(conn, table, col)
            if bad:
                findings.append(Finding("WARN", f"Non-ISO-ish dates in {table}.{col} (sample): {bad}"))

        # Relationship ordering invariant.
        bad_pairs = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM relationships
            WHERE person_low_id >= person_high_id;
            """
        ).fetchone()["n"]
        if bad_pairs:
            findings.append(Finding("ERROR", f"relationships has {bad_pairs} rows where person_low_id >= person_high_id"))

    finally:
        conn.close()

    # Print report
    print(f"Audit DB: {db_path}")
    for f in findings:
        print(f"[{f.level}] {f.message}")

    levels = {f.level for f in findings}
    if "ERROR" in levels:
        raise SystemExit(2)
    if args.fail_on_warn and "WARN" in levels:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
