from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _int(s: Any, *, default: int = 0) -> int:
    v = _clean(s)
    if not v:
        return default
    try:
        return int(v)
    except ValueError as e:
        raise SystemExit(f"Expected int, got {v!r}") from e


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_lookup_relationship_type(conn: sqlite3.Connection, code: str, label: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO lkp_relationship_type (relationship_type_code, label) VALUES (?, ?)",
        (code, label),
    )


def _get_or_create_source(
    conn: sqlite3.Connection,
    *,
    source_type_code: str,
    title: str,
    creator: Optional[str],
    date_created: Optional[str],
    citation_full: Optional[str],
    notes: Optional[str],
) -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_type_code = ? AND title = ? ORDER BY source_id ASC LIMIT 1",
        (source_type_code, title),
    ).fetchone()
    if row:
        return int(row[0])

    cur = conn.execute(
        """
        INSERT INTO sources (
          source_type_code,
          title,
          creator,
          date_created,
          citation_full,
          notes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_type_code, title, creator, date_created, citation_full, notes),
    )
    return int(cur.lastrowid)


def _find_person_id_by_name(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        """
        SELECT person_id
        FROM people
        WHERE full_name = ? OR display_name = ?
        ORDER BY person_id ASC
        LIMIT 1
        """,
        (name, name),
    ).fetchone()
    if not row:
        raise SystemExit(f"Could not find person by name {name!r} in people table.")
    return int(row[0])


def _find_people_review_person_id(conn: sqlite3.Connection, *, full_name: str, display_name: str) -> Optional[int]:
    # Prefer the person row that came from people_review import, but fall back to any exact name match.
    # This keeps the script usable even when some staged names matched pre-existing demo seed rows.

    candidates = [full_name, display_name]
    candidates = [c for c in candidates if _clean(c)]
    if not candidates:
        return None

    # 1) Prefer people_review-derived rows.
    for name in candidates:
        rows = conn.execute(
            """
            SELECT person_id
            FROM people
            WHERE (full_name = ? OR display_name = ?)
              AND notes LIKE 'From people_review%'
            ORDER BY person_id ASC
            """,
            (name, name),
        ).fetchall()
        if len(rows) == 1:
            return int(rows[0][0])
        if len(rows) > 1:
            raise SystemExit(
                f"Ambiguous match for {name!r} in people_review-derived rows ({len(rows)} matches)."
            )

    # 2) Fallback to any exact name match.
    for name in candidates:
        rows = conn.execute(
            """
            SELECT person_id
            FROM people
            WHERE (full_name = ? OR display_name = ?)
            ORDER BY person_id ASC
            """,
            (name, name),
        ).fetchall()
        if len(rows) == 1:
            return int(rows[0][0])
        if len(rows) > 1:
            raise SystemExit(f"Ambiguous match for {name!r} in people table ({len(rows)} matches).")

    return None


def _strength_from_letters_count(n: int) -> int:
    # Map a (letters) count into the schema's 1–3 strength.
    if n <= 2:
        return 1
    if n <= 10:
        return 2
    return 3


@dataclass(frozen=True)
class Target:
    canonical_key: str
    full_name: str
    display_name: str
    mention_letters_count: int


def _read_review_counts(review_csv: Path) -> Dict[str, int]:
    if not review_csv.exists() or review_csv.stat().st_size == 0:
        raise SystemExit(f"Missing or empty review CSV: {review_csv}")

    counts: Dict[str, int] = defaultdict(int)
    with review_csv.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        required = {"canonical_key", "action", "mention_letters_count"}
        if not r.fieldnames or any(c not in r.fieldnames for c in required):
            raise SystemExit(f"Review CSV missing required columns {sorted(required)}: {review_csv}")

        for i, row in enumerate(r, start=2):
            action = _clean(row.get("action")).lower() or "review"
            if action not in {"keep", "merge", "drop", "review"}:
                raise SystemExit(f"Invalid action {action!r} at {review_csv}:{i}")
            if action not in {"keep", "merge"}:
                continue

            key = _clean(row.get("canonical_key"))
            if not key:
                raise SystemExit(f"Empty canonical_key at {review_csv}:{i}")

            counts[key] += _int(row.get("mention_letters_count"), default=0)

    return dict(counts)


def _read_people_staging(people_staging_csv: Path) -> list[Tuple[str, str, str]]:
    if not people_staging_csv.exists() or people_staging_csv.stat().st_size == 0:
        raise SystemExit(f"Missing or empty people staging CSV: {people_staging_csv}")

    out: list[Tuple[str, str, str]] = []
    with people_staging_csv.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        required = {"canonical_key", "full_name", "display_name"}
        if not r.fieldnames or any(c not in r.fieldnames for c in required):
            raise SystemExit(f"People staging CSV missing required columns {sorted(required)}: {people_staging_csv}")

        for i, row in enumerate(r, start=2):
            key = _clean(row.get("canonical_key"))
            if not key:
                raise SystemExit(f"Empty canonical_key at {people_staging_csv}:{i}")
            full_name = _clean(row.get("full_name"))
            display_name = _clean(row.get("display_name"))
            out.append((key, full_name, display_name))

    return out


def link(
    *,
    db_path: Path,
    anchor_person_id: int,
    review_csv: Path,
    people_staging_csv: Path,
    relationship_type_code: str,
    relationship_type_label: str,
    source_type_code: str,
    source_title: str,
    source_creator: Optional[str],
    source_date_created: Optional[str],
    source_citation_full: Optional[str],
    source_notes: Optional[str],
    start_date: str,
    end_date: str,
    dry_run: bool,
) -> None:
    review_counts = _read_review_counts(review_csv)
    staged_people = _read_people_staging(people_staging_csv)

    targets: list[Target] = []
    for key, full_name, display_name in staged_people:
        targets.append(
            Target(
                canonical_key=key,
                full_name=full_name,
                display_name=display_name,
                mention_letters_count=review_counts.get(key, 0),
            )
        )

    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")

        _ensure_lookup_relationship_type(conn, relationship_type_code, relationship_type_label)
        source_id = _get_or_create_source(
            conn,
            source_type_code=source_type_code,
            title=source_title,
            creator=source_creator,
            date_created=source_date_created,
            citation_full=source_citation_full,
            notes=source_notes,
        )

        inserted = 0
        skipped = 0
        missing = 0

        for t in targets:
            target_id = _find_people_review_person_id(conn, full_name=t.full_name, display_name=t.display_name)
            if target_id is None:
                missing += 1
                continue
            if target_id == anchor_person_id:
                continue

            low_id, high_id = (anchor_person_id, target_id) if anchor_person_id < target_id else (target_id, anchor_person_id)
            strength = _strength_from_letters_count(t.mention_letters_count)

            notes = (
                f"Corpus-derived link from {source_title}. "
                f"canonical_key={t.canonical_key}; mention_letters_count={t.mention_letters_count}"
            )

            if dry_run:
                inserted += 1
                continue

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO relationships (
                  person_low_id,
                  person_high_id,
                  relationship_type_code,
                  start_date,
                  end_date,
                  strength,
                  source_id,
                  notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (low_id, high_id, relationship_type_code, start_date, end_date, strength, source_id, notes),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Linked corpus-derived people")
        print(f"  DB: {db_path}")
        print(f"  Anchor person_id: {anchor_person_id}")
        print(f"  Relationship type: {relationship_type_code}")
        print(f"  Source: {source_id} ({source_title})")
        print("Results")
        print(f"  Candidates (staging): {len(targets)}")
        print(f"  Inserted: {inserted}{' (dry-run)' if dry_run else ''}")
        print(f"  Skipped existing: {skipped}")
        print(f"  Missing person matches: {missing}")

    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Create corpus-derived relationships from an anchor person (e.g., BF Perry) to every person loaded from "
            "people_review_edited.csv (via unionism_people_staging.csv)."
        )
    )
    p.add_argument("--db", default="unionism.db", help="SQLite DB path")
    p.add_argument(
        "--anchor-person-id",
        type=int,
        default=None,
        help="Anchor person_id (default: look up by --anchor-name)",
    )
    p.add_argument("--anchor-name", default="Benjamin Franklin Perry", help="Anchor person full/display name")
    p.add_argument("--review-csv", default="data/staging/people_review_edited.csv")
    p.add_argument("--people-staging-csv", default="data/staging/unionism_people_staging.csv")
    p.add_argument("--relationship-type-code", default="corpus_mention")
    p.add_argument("--relationship-type-label", default="Corpus-derived mention link")
    p.add_argument("--source-type-code", default="letter")
    p.add_argument("--source-title", default="B. F. Perry letters (corpus)")
    p.add_argument("--source-creator", default="NER extraction pipeline")
    p.add_argument("--source-date-created", default=None)
    p.add_argument(
        "--source-citation-full",
        default="Corpus-derived people graph from B. F. Perry letters (placeholder citation; replace with archival citation).",
    )
    p.add_argument(
        "--source-notes",
        default="Auto-generated edges to indicate people connected via BF Perry letters corpus; not a claim of direct relationship.",
    )
    p.add_argument("--start-date", default="1817-01-01")
    p.add_argument("--end-date", default="1865-12-31")
    p.add_argument("--dry-run", action="store_true")

    args = p.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    conn = _connect((repo_root / args.db).resolve())
    try:
        if args.anchor_person_id is None:
            anchor_id = _find_person_id_by_name(conn, args.anchor_name)
        else:
            anchor_id = int(args.anchor_person_id)
    finally:
        conn.close()

    link(
        db_path=(repo_root / args.db).resolve(),
        anchor_person_id=anchor_id,
        review_csv=(repo_root / args.review_csv).resolve(),
        people_staging_csv=(repo_root / args.people_staging_csv).resolve(),
        relationship_type_code=args.relationship_type_code,
        relationship_type_label=args.relationship_type_label,
        source_type_code=args.source_type_code,
        source_title=args.source_title,
        source_creator=args.source_creator,
        source_date_created=args.source_date_created,
        source_citation_full=args.source_citation_full,
        source_notes=args.source_notes,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    main()
