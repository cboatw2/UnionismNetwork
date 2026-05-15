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
class EventRow:
    event_id: Optional[int]
    event_name: str
    event_type_code: str
    start_date: Optional[str]
    end_date: Optional[str]
    place_id: Optional[int]
    place_name: Optional[str]
    place_type_code: Optional[str]
    description: Optional[str]


REQUIRED_COLUMNS = {"event_name", "event_type_code"}


def _resolve_place_id(conn: sqlite3.Connection, row: EventRow) -> Optional[int]:
    if row.place_id is not None:
        ok = conn.execute("SELECT 1 FROM places WHERE place_id = ?", (row.place_id,)).fetchone()
        if not ok:
            raise SystemExit(f"place_id not found: {row.place_id}")
        return row.place_id

    if not row.place_name:
        return None

    name = _clean(row.place_name)
    typ = _clean(row.place_type_code) or ""
    if not typ:
        raise SystemExit(f"When place_name is set, place_type_code is required (place_name={name!r})")

    rows = conn.execute(
        """
        SELECT place_id
        FROM places
        WHERE place_name = ?
          AND place_type_code = ?
        ORDER BY place_id ASC
        """,
        (name, typ),
    ).fetchall()

    if not rows:
        raise SystemExit(f"Could not resolve event place: name={name!r} type={typ!r}")
    if len(rows) > 1:
        raise SystemExit(f"Ambiguous event place: name={name!r} type={typ!r} ({len(rows)} matches)")
    return int(rows[0][0])


def _find_existing_event_id(conn: sqlite3.Connection, *, event_name: str, event_type_code: str, start_date: Optional[str], place_id: Optional[int]) -> Optional[int]:
    # Conservative natural key: name + type + start_date + place_id.
    rows = conn.execute(
        """
        SELECT event_id
        FROM events
        WHERE event_name = ?
          AND event_type_code = ?
          AND ( (start_date IS NULL AND ? IS NULL) OR start_date = ? )
          AND ( (place_id IS NULL AND ? IS NULL) OR place_id = ? )
        ORDER BY event_id ASC
        """,
        (event_name, event_type_code, start_date, start_date, place_id, place_id),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise SystemExit(
            f"Ambiguous event match for (name,type,start,place)={event_name!r},{event_type_code!r},{start_date!r},{place_id!r} ({len(rows)} matches)"
        )
    return int(rows[0][0])


def _merge_update_event(conn: sqlite3.Connection, *, event_id: int, start_date: Optional[str], end_date: Optional[str], place_id: Optional[int], description: Optional[str], overwrite: bool) -> bool:
    current = conn.execute(
        "SELECT start_date, end_date, place_id, description FROM events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if not current:
        raise SystemExit(f"event_id not found for update: {event_id}")

    updates: dict[str, Any] = {}

    def consider(col: str, val: Any) -> None:
        if val is None:
            return
        if overwrite or current[col] is None:
            updates[col] = val

    consider("start_date", start_date)
    consider("end_date", end_date)
    consider("place_id", place_id)
    consider("description", description)

    if not updates:
        return False

    sets = ", ".join([f"{k} = ?" for k in updates.keys()])
    params = tuple(updates.values()) + (event_id,)
    conn.execute(f"UPDATE events SET {sets} WHERE event_id = ?", params)
    return True


def load_events(*, db_path: Path, csv_path: Path, dry_run: bool, overwrite: bool) -> None:
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
        matched_existing = 0
        updated_existing = 0

        for i, r in enumerate(rows, start=2):
            row = EventRow(
                event_id=_int_or_none(r.get("event_id")),
                event_name=_clean(r.get("event_name")),
                event_type_code=_clean(r.get("event_type_code")),
                start_date=_none_if_empty(r.get("start_date")),
                end_date=_none_if_empty(r.get("end_date")),
                place_id=_int_or_none(r.get("place_id")),
                place_name=_none_if_empty(r.get("place_name")),
                place_type_code=_none_if_empty(r.get("place_type_code")),
                description=_none_if_empty(r.get("description")),
            )

            if not row.event_name or not row.event_type_code:
                raise SystemExit(f"Missing required fields at {csv_path}:{i}")

            ok_type = conn.execute(
                "SELECT 1 FROM lkp_event_type WHERE event_type_code = ?",
                (row.event_type_code,),
            ).fetchone()
            if not ok_type:
                raise SystemExit(f"Unknown event_type_code at {csv_path}:{i}: {row.event_type_code!r}")

            place_id = _resolve_place_id(conn, row)

            event_id: Optional[int] = None
            if row.event_id is not None:
                exists = conn.execute("SELECT 1 FROM events WHERE event_id = ?", (row.event_id,)).fetchone()
                if not exists:
                    raise SystemExit(f"event_id not found at {csv_path}:{i}: {row.event_id}")
                event_id = row.event_id
            else:
                event_id = _find_existing_event_id(
                    conn,
                    event_name=row.event_name,
                    event_type_code=row.event_type_code,
                    start_date=row.start_date,
                    place_id=place_id,
                )

            if event_id is None:
                if dry_run:
                    inserted += 1
                    continue

                cur = conn.execute(
                    """
                    INSERT INTO events (
                      event_name,
                      event_type_code,
                      start_date,
                      end_date,
                      place_id,
                      description
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (row.event_name, row.event_type_code, row.start_date, row.end_date, place_id, row.description),
                )
                inserted += 1
                event_id = int(cur.lastrowid)
            else:
                matched_existing += 1

            if event_id is not None and not dry_run:
                changed = _merge_update_event(
                    conn,
                    event_id=event_id,
                    start_date=row.start_date,
                    end_date=row.end_date,
                    place_id=place_id,
                    description=row.description,
                    overwrite=overwrite,
                )
                if changed:
                    updated_existing += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Loaded events staging")
        print(f"  DB: {db_path}")
        print(f"  CSV: {csv_path} ({len(rows)} rows)")
        print("Results")
        print(f"  Inserted: {inserted}{' (dry-run)' if dry_run else ''}")
        print(f"  Matched existing: {matched_existing}")
        print(f"  Updated existing: {updated_existing}")

    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Load events into unionism.db from a staging CSV.")
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument("--csv", default="data/staging/events_staging.csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite non-NULL DB values when the staging row provides a non-NULL value (default is fill-NULLs only).",
    )

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    load_events(
        db_path=(repo_root / args.db).resolve(),
        csv_path=(repo_root / args.csv).resolve(),
        dry_run=bool(args.dry_run),
        overwrite=bool(args.overwrite),
    )


if __name__ == "__main__":
    main()
