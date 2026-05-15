from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Any, Optional, Tuple


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _none_if_empty(s: Any) -> Optional[str]:
    v = _clean(s)
    return v if v else None


def _int_or_none(s: Any) -> Optional[int]:
    v = _clean(s)
    if not v:
        return None
    try:
        return int(v)
    except ValueError as e:
        raise SystemExit(f"Expected integer, got {v!r}") from e


def _bool_int(s: Any, *, default: int = 0) -> int:
    v = _clean(s)
    if v == "":
        return default
    if v in ("0", "1"):
        return int(v)
    if v.lower() in ("true", "false"):
        return 1 if v.lower() == "true" else 0
    raise SystemExit(f"Expected 0/1 or true/false, got {v!r}")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _resolve_person_token(conn: sqlite3.Connection, token: str) -> int:
    t = _clean(token)
    if not t:
        raise SystemExit("person_a/person_b cannot be empty")

    # Accept either a person_id integer or an exact display/full name.
    try:
        pid = int(t)
    except ValueError:
        pid = None

    if pid is not None:
        row = conn.execute("SELECT 1 FROM people WHERE person_id = ?", (pid,)).fetchone()
        if not row:
            raise SystemExit(f"person_id not found: {pid}")
        return pid

    rows = conn.execute(
        "SELECT person_id FROM people WHERE full_name = ? OR display_name = ? ORDER BY person_id ASC",
        (t, t),
    ).fetchall()
    if not rows:
        raise SystemExit(f"Could not resolve person name to person_id: {t!r}")
    if len(rows) > 1:
        # Prefer the row created from people_review if available.
        pref = conn.execute(
            """
            SELECT person_id
            FROM people
            WHERE (full_name = ? OR display_name = ?)
              AND notes LIKE 'From people_review%'
            ORDER BY person_id ASC
            """,
            (t, t),
        ).fetchall()
        if len(pref) == 1:
            return int(pref[0][0])
        raise SystemExit(f"Ambiguous person name {t!r} ({len(rows)} matches)")

    return int(rows[0][0])


def _ensure_lookup_relationship_type(conn: sqlite3.Connection, code: str, label: str) -> None:
    # Allow creating new relationship types for manual coding.
    conn.execute(
        "INSERT OR IGNORE INTO lkp_relationship_type (relationship_type_code, label) VALUES (?, ?)",
        (code, label),
    )


def _get_or_create_source(
    conn: sqlite3.Connection,
    *,
    source_id: Optional[int],
    source_type_code: Optional[str],
    title: Optional[str],
    creator: Optional[str],
    date_created: Optional[str],
    citation_full: Optional[str],
    notes: Optional[str],
) -> int:
    if source_id is not None:
        row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        if not row:
            raise SystemExit(f"source_id not found in sources: {source_id}")
        return source_id

    t = _clean(title)
    if not t:
        raise SystemExit("Each row must include source_id, or provide source_title to create/find a source")

    st = _clean(source_type_code) or "other"

    existing = conn.execute(
        "SELECT source_id FROM sources WHERE source_type_code = ? AND title = ? ORDER BY source_id ASC LIMIT 1",
        (st, t),
    ).fetchone()
    if existing:
        return int(existing[0])

    cur = conn.execute(
        """
        INSERT INTO sources (source_type_code, title, creator, date_created, citation_full, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (st, t, _none_if_empty(creator), _none_if_empty(date_created), _none_if_empty(citation_full), _none_if_empty(notes)),
    )
    return int(cur.lastrowid)


def _get_or_create_relationship(
    conn: sqlite3.Connection,
    *,
    relationship_id: Optional[int],
    person_a_id: int,
    person_b_id: int,
    relationship_type_code: str,
    baseline_start_date: Optional[str],
    baseline_end_date: Optional[str],
    baseline_strength: Optional[int],
    baseline_alignment_status_code: Optional[str],
    baseline_source_id: Optional[int],
    baseline_notes: Optional[str],
) -> int:
    if relationship_id is not None:
        row = conn.execute(
            "SELECT relationship_id FROM relationships WHERE relationship_id = ?",
            (relationship_id,),
        ).fetchone()
        if not row:
            raise SystemExit(f"relationship_id not found: {relationship_id}")
        return int(row[0])

    low_id, high_id = (person_a_id, person_b_id) if person_a_id < person_b_id else (person_b_id, person_a_id)

    if baseline_start_date:
        rows = conn.execute(
            """
            SELECT relationship_id
            FROM relationships
            WHERE person_low_id = ?
              AND person_high_id = ?
              AND relationship_type_code = ?
              AND start_date = ?
            ORDER BY relationship_id ASC
            """,
            (low_id, high_id, relationship_type_code, baseline_start_date),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT relationship_id
            FROM relationships
            WHERE person_low_id = ?
              AND person_high_id = ?
              AND relationship_type_code = ?
              AND start_date IS NULL
            ORDER BY relationship_id ASC
            """,
            (low_id, high_id, relationship_type_code),
        ).fetchall()

    if len(rows) == 1:
        return int(rows[0][0])
    if len(rows) > 1:
        raise SystemExit(
            f"Ambiguous baseline relationship match for pair=({low_id},{high_id}) type={relationship_type_code!r} start_date={baseline_start_date!r}"
        )

    cur = conn.execute(
        """
        INSERT INTO relationships (
          person_low_id,
          person_high_id,
          relationship_type_code,
          start_date,
          end_date,
          strength,
          alignment_status_code,
          source_id,
          notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            low_id,
            high_id,
            relationship_type_code,
            baseline_start_date,
            baseline_end_date,
            baseline_strength,
            baseline_alignment_status_code,
            baseline_source_id,
            baseline_notes,
        ),
    )
    return int(cur.lastrowid)


REQUIRED_COLUMNS = {
    "person_a",
    "person_b",
    "relationship_type_code",
    "issue_category_code",
    "alignment_status_code",
    "claim_type_code",
    "confidence_score",
    "evidence_type_code",
    "justification_note",
}


def load(*, db_path: Path, csv_path: Path, dry_run: bool) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty CSV: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"Could not read header from: {csv_path}")
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise SystemExit(f"CSV missing required columns {missing}: {csv_path}")
        rows = list(reader)

    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")

        inserted_char = 0
        skipped_char = 0
        created_relationships = 0
        created_sources = 0

        for i, r in enumerate(rows, start=2):
            a_id = _resolve_person_token(conn, _clean(r.get("person_a")))
            b_id = _resolve_person_token(conn, _clean(r.get("person_b")))
            rel_type = _clean(r.get("relationship_type_code"))
            if not rel_type:
                raise SystemExit(f"Missing relationship_type_code at {csv_path}:{i}")

            # Ensure the relationship type exists (label defaults to code).
            _ensure_lookup_relationship_type(conn, rel_type, rel_type)

            rel_id_before = conn.execute("SELECT count(*) FROM relationships").fetchone()[0]
            relationship_id = _get_or_create_relationship(
                conn,
                relationship_id=_int_or_none(r.get("relationship_id")),
                person_a_id=a_id,
                person_b_id=b_id,
                relationship_type_code=rel_type,
                baseline_start_date=_none_if_empty(r.get("baseline_start_date")),
                baseline_end_date=_none_if_empty(r.get("baseline_end_date")),
                baseline_strength=_int_or_none(r.get("baseline_strength")),
                baseline_alignment_status_code=_none_if_empty(r.get("baseline_alignment_status_code")),
                baseline_source_id=_int_or_none(r.get("baseline_source_id")),
                baseline_notes=_none_if_empty(r.get("baseline_notes")),
            )
            rel_id_after = conn.execute("SELECT count(*) FROM relationships").fetchone()[0]
            if rel_id_after > rel_id_before:
                created_relationships += 1

            src_before = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
            source_id = _get_or_create_source(
                conn,
                source_id=_int_or_none(r.get("source_id")),
                source_type_code=_none_if_empty(r.get("source_type_code")),
                title=_none_if_empty(r.get("source_title")),
                creator=_none_if_empty(r.get("source_creator")),
                date_created=_none_if_empty(r.get("source_date_created")),
                citation_full=_none_if_empty(r.get("source_citation_full")),
                notes=_none_if_empty(r.get("source_notes")),
            )
            src_after = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
            if src_after > src_before:
                created_sources += 1

            issue = _clean(r.get("issue_category_code"))
            align = _clean(r.get("alignment_status_code"))
            claim = _clean(r.get("claim_type_code"))
            conf = _int_or_none(r.get("confidence_score"))
            evidence = _clean(r.get("evidence_type_code"))
            just = _clean(r.get("justification_note"))
            if not (issue and align and claim and evidence and just and conf is not None):
                raise SystemExit(f"Missing required characterization fields at {csv_path}:{i}")

            params = (
                relationship_id,
                _int_or_none(r.get("event_id")),
                _none_if_empty(r.get("date_start")),
                _none_if_empty(r.get("date_end")),
                issue,
                _none_if_empty(r.get("scale_level_code")),
                align,
                _int_or_none(r.get("strength")),
                claim,
                int(conf),
                evidence,
                _bool_int(r.get("counterevidence_present"), default=0),
                source_id,
                just,
                _none_if_empty(r.get("notes")),
            )

            if dry_run:
                inserted_char += 1
                continue

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO relationship_characterizations (
                  relationship_id,
                  event_id,
                  date_start,
                  date_end,
                  issue_category_code,
                  scale_level_code,
                  alignment_status_code,
                  strength,
                  claim_type_code,
                  confidence_score,
                  evidence_type_code,
                  counterevidence_present,
                  source_id,
                  justification_note,
                  notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            if cur.rowcount == 1:
                inserted_char += 1
            else:
                skipped_char += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Loaded relationship characterizations staging")
        print(f"  DB: {db_path}")
        print(f"  CSV: {csv_path} ({len(rows)} rows)")
        print("Results")
        print(f"  Characterizations inserted: {inserted_char}{' (dry-run)' if dry_run else ''}")
        print(f"  Characterizations skipped (duplicate): {skipped_char}")
        print(f"  Baseline relationships created: {created_relationships}")
        print(f"  Sources created: {created_sources}")

    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Load manual issue-specific relationship characterizations from a staging CSV into unionism.db. "
            "If relationship_id is blank, a baseline relationships row is created/located for (person_a, person_b, relationship_type_code)."
        )
    )
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument("--csv", default="data/staging/relationship_characterizations_staging.csv")
    ap.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    load(
        db_path=(repo_root / args.db).resolve(),
        csv_path=(repo_root / args.csv).resolve(),
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    main()
