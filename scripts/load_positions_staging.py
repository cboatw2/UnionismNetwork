from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


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


def _float_or_none(s: Any) -> Optional[float]:
    v = _clean(s)
    if not v:
        return None
    try:
        return float(v)
    except ValueError as e:
        raise SystemExit(f"Expected number, got {v!r}") from e


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


def _get_single_id(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> Optional[int]:
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise SystemExit(f"Ambiguous lookup for params={params} ({len(rows)} matches)")
    return int(rows[0][0])


def _resolve_person_id(conn: sqlite3.Connection, person_id: Optional[int], person_name: Optional[str]) -> int:
    if person_id is not None:
        row = conn.execute("SELECT 1 FROM people WHERE person_id = ?", (person_id,)).fetchone()
        if not row:
            raise SystemExit(f"person_id not found in people: {person_id}")
        return person_id

    name = _clean(person_name)
    if not name:
        raise SystemExit("Each row must include either person_id or person_name")

    pid = _get_single_id(
        conn,
        "SELECT person_id FROM people WHERE full_name = ? OR display_name = ? ORDER BY person_id ASC",
        (name, name),
    )
    if pid is None:
        raise SystemExit(f"Could not resolve person_name to a unique person_id: {name!r}")
    return pid


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


REQUIRED_COLUMNS = {
    "issue_category_code",
    "position_label_code",
    "scale_level_code",
    "claim_type_code",
    "confidence_score",
    "evidence_type_code",
    "justification_note",
}


def load_positions(*, db_path: Path, csv_path: Path, dry_run: bool) -> None:
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

        inserted = 0
        skipped = 0
        created_sources = 0

        for i, r in enumerate(rows, start=2):
            person_id = _int_or_none(r.get("person_id"))
            person_name = _none_if_empty(r.get("person_name"))
            pid = _resolve_person_id(conn, person_id, person_name)

            issue = _clean(r.get("issue_category_code"))
            label = _clean(r.get("position_label_code"))
            scale = _clean(r.get("scale_level_code"))
            claim_type = _clean(r.get("claim_type_code"))
            conf = _int_or_none(r.get("confidence_score"))
            evidence = _clean(r.get("evidence_type_code"))
            just = _clean(r.get("justification_note"))

            if not (issue and label and scale and claim_type and evidence and just and conf is not None):
                raise SystemExit(f"Missing required fields at {csv_path}:{i}")

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

            params = (
                pid,
                _int_or_none(r.get("event_id")),
                _none_if_empty(r.get("date_start")),
                _none_if_empty(r.get("date_end")),
                issue,
                label,
                _float_or_none(r.get("ideology_score")),
                scale,
                _none_if_empty(r.get("region_relevance_code")),
                _float_or_none(r.get("stance_on_union")),
                _float_or_none(r.get("stance_on_states_rights")),
                _float_or_none(r.get("stance_on_slavery")),
                _float_or_none(r.get("stance_on_secession")),
                claim_type,
                int(conf),
                evidence,
                _bool_int(r.get("counterevidence_present"), default=0),
                source_id,
                just,
                _none_if_empty(r.get("interpretive_note")),
            )

            if dry_run:
                inserted += 1
                continue

            cur = conn.execute(
                """
                INSERT INTO positions (
                  person_id,
                  event_id,
                  date_start,
                  date_end,
                  issue_category_code,
                  position_label_code,
                  ideology_score,
                  scale_level_code,
                  region_relevance_code,
                  stance_on_union,
                  stance_on_states_rights,
                  stance_on_slavery,
                  stance_on_secession,
                  claim_type_code,
                  confidence_score,
                  evidence_type_code,
                  counterevidence_present,
                  source_id,
                  justification_note,
                  interpretive_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Loaded positions staging")
        print(f"  DB: {db_path}")
        print(f"  CSV: {csv_path} ({len(rows)} rows)")
        print("Results")
        print(f"  Inserted: {inserted}{' (dry-run)' if dry_run else ''}")
        print(f"  Skipped: {skipped}")
        print(f"  Sources created: {created_sources}")

    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Load manual issue positions into unionism.db from a staging CSV.")
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument("--csv", default="data/staging/positions_staging.csv")
    ap.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    load_positions(
        db_path=(repo_root / args.db).resolve(),
        csv_path=(repo_root / args.csv).resolve(),
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    main()
