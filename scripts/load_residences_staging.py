from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


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


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@dataclass(frozen=True)
class ResidenceRow:
    residence_id: Optional[int]
    person_id: Optional[int]
    person_name: Optional[str]
    place_id: Optional[int]
    place_name: Optional[str]
    place_type_code: Optional[str]
    residence_type_code: Optional[str]
    date_start: Optional[str]
    date_end: Optional[str]
    source_id: Optional[int]
    source_type_code: Optional[str]
    source_title: Optional[str]
    source_creator: Optional[str]
    source_date_created: Optional[str]
    source_citation_full: Optional[str]
    source_notes: Optional[str]
    notes: Optional[str]


REQUIRED_COLUMNS = {"date_start"}  # plus either (person_id|person_name) and (place_id|place_name+place_type_code)


def _get_single_id(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> Optional[int]:
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise SystemExit(f"Ambiguous lookup for params={params} ({len(rows)} matches)")
    return int(rows[0][0])


def _resolve_person_id(conn: sqlite3.Connection, person_id: Optional[int], person_name: Optional[str]) -> int:
    if person_id is not None:
        ok = conn.execute("SELECT 1 FROM people WHERE person_id = ?", (person_id,)).fetchone()
        if not ok:
            raise SystemExit(f"person_id not found: {person_id}")
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


def _resolve_place_id(conn: sqlite3.Connection, place_id: Optional[int], place_name: Optional[str], place_type_code: Optional[str]) -> int:
    if place_id is not None:
        ok = conn.execute("SELECT 1 FROM places WHERE place_id = ?", (place_id,)).fetchone()
        if not ok:
            raise SystemExit(f"place_id not found: {place_id}")
        return place_id

    name = _clean(place_name)
    if not name:
        raise SystemExit("Each row must include either place_id or place_name")

    typ = _clean(place_type_code)
    if not typ:
        raise SystemExit(f"place_type_code is required when place_name is set (place_name={name!r})")

    pid = _get_single_id(
        conn,
        "SELECT place_id FROM places WHERE place_name = ? AND place_type_code = ? ORDER BY place_id ASC",
        (name, typ),
    )
    if pid is None:
        raise SystemExit(f"Could not resolve place to a unique place_id: name={name!r} type={typ!r}")
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
        ok = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        if not ok:
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

        inserted = 0
        created_sources = 0

        for i, r in enumerate(rows, start=2):
            row = ResidenceRow(
                residence_id=_int_or_none(r.get("residence_id")),
                person_id=_int_or_none(r.get("person_id")),
                person_name=_none_if_empty(r.get("person_name")),
                place_id=_int_or_none(r.get("place_id")),
                place_name=_none_if_empty(r.get("place_name")),
                place_type_code=_none_if_empty(r.get("place_type_code")),
                residence_type_code=_none_if_empty(r.get("residence_type_code")),
                date_start=_none_if_empty(r.get("date_start")),
                date_end=_none_if_empty(r.get("date_end")),
                source_id=_int_or_none(r.get("source_id")),
                source_type_code=_none_if_empty(r.get("source_type_code")),
                source_title=_none_if_empty(r.get("source_title")),
                source_creator=_none_if_empty(r.get("source_creator")),
                source_date_created=_none_if_empty(r.get("source_date_created")),
                source_citation_full=_none_if_empty(r.get("source_citation_full")),
                source_notes=_none_if_empty(r.get("source_notes")),
                notes=_none_if_empty(r.get("notes")),
            )

            if not row.date_start:
                raise SystemExit(f"Missing date_start at {csv_path}:{i}")

            person_id = _resolve_person_id(conn, row.person_id, row.person_name)
            place_id = _resolve_place_id(conn, row.place_id, row.place_name, row.place_type_code)

            if row.residence_type_code:
                ok = conn.execute(
                    "SELECT 1 FROM lkp_residence_type WHERE residence_type_code = ?",
                    (row.residence_type_code,),
                ).fetchone()
                if not ok:
                    raise SystemExit(f"Unknown residence_type_code at {csv_path}:{i}: {row.residence_type_code!r}")

            src_before = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
            source_id = _get_or_create_source(
                conn,
                source_id=row.source_id,
                source_type_code=row.source_type_code,
                title=row.source_title,
                creator=row.source_creator,
                date_created=row.source_date_created,
                citation_full=row.source_citation_full,
                notes=row.source_notes,
            )
            src_after = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
            if src_after > src_before:
                created_sources += 1

            if dry_run:
                inserted += 1
                continue

            conn.execute(
                """
                INSERT INTO person_place_residence (
                  person_id,
                  place_id,
                  residence_type_code,
                  date_start,
                  date_end,
                  source_id,
                  notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    place_id,
                    row.residence_type_code,
                    row.date_start,
                    row.date_end,
                    source_id,
                    row.notes,
                ),
            )
            inserted += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Loaded residences staging")
        print(f"  DB: {db_path}")
        print(f"  CSV: {csv_path} ({len(rows)} rows)")
        print("Results")
        print(f"  Inserted: {inserted}{' (dry-run)' if dry_run else ''}")
        print(f"  Sources created: {created_sources}")

    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Load person_place_residence rows into unionism.db from a staging CSV.")
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument("--csv", default="data/staging/residences_staging.csv")
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
