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


def _float_or_none(s: Any) -> Optional[float]:
    v = _clean(s)
    if not v:
        return None
    try:
        return float(v)
    except ValueError as e:
        raise SystemExit(f"Expected number, got {v!r}") from e


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@dataclass(frozen=True)
class PlaceRow:
    place_id: Optional[int]
    place_name: str
    place_type_code: str
    parent_place_id: Optional[int]
    parent_place_name: Optional[str]
    parent_place_type_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    region_sc_code: Optional[str]
    modern_state: Optional[str]
    notes: Optional[str]


REQUIRED_COLUMNS = {"place_name", "place_type_code"}


def _resolve_parent_place_id(conn: sqlite3.Connection, row: PlaceRow) -> Optional[int]:
    if row.parent_place_id is not None:
        ok = conn.execute("SELECT 1 FROM places WHERE place_id = ?", (row.parent_place_id,)).fetchone()
        if not ok:
            raise SystemExit(f"parent_place_id not found: {row.parent_place_id}")
        return row.parent_place_id

    if not row.parent_place_name:
        return None

    parent_name = _clean(row.parent_place_name)
    parent_type = _clean(row.parent_place_type_code) or ""
    if not parent_type:
        raise SystemExit(
            f"When parent_place_name is set, parent_place_type_code is required (parent_place_name={parent_name!r})"
        )

    rows = conn.execute(
        """
        SELECT place_id
        FROM places
        WHERE place_name = ?
          AND place_type_code = ?
        ORDER BY place_id ASC
        """,
        (parent_name, parent_type),
    ).fetchall()

    if not rows:
        raise SystemExit(f"Could not resolve parent place: name={parent_name!r} type={parent_type!r}")
    if len(rows) > 1:
        raise SystemExit(f"Ambiguous parent place: name={parent_name!r} type={parent_type!r} ({len(rows)} matches)")
    return int(rows[0][0])


def _place_lookup(conn: sqlite3.Connection, *, place_name: str, place_type_code: str, parent_place_id: Optional[int]) -> Optional[int]:
    rows = conn.execute(
        """
        SELECT place_id
        FROM places
        WHERE place_name = ?
          AND place_type_code = ?
          AND ( (parent_place_id IS NULL AND ? IS NULL) OR parent_place_id = ? )
        ORDER BY place_id ASC
        """,
        (place_name, place_type_code, parent_place_id, parent_place_id),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise SystemExit(
            f"Ambiguous place match for (name,type,parent)={place_name!r},{place_type_code!r},{parent_place_id!r} ({len(rows)} matches)"
        )
    return int(rows[0][0])


def _apply_merge_update(
    conn: sqlite3.Connection,
    *,
    place_id: int,
    latitude: Optional[float],
    longitude: Optional[float],
    region_sc_code: Optional[str],
    modern_state: Optional[str],
    notes: Optional[str],
    overwrite: bool,
) -> None:
    # We only write non-NULL staged values. If overwrite=False, we only fill NULLs in DB.
    current = conn.execute(
        "SELECT latitude, longitude, region_sc_code, modern_state, notes FROM places WHERE place_id = ?",
        (place_id,),
    ).fetchone()
    if not current:
        raise SystemExit(f"place_id not found for update: {place_id}")

    updates: dict[str, Any] = {}

    def consider(col: str, val: Any) -> None:
        if val is None:
            return
        if overwrite or current[col] is None:
            updates[col] = val

    consider("latitude", latitude)
    consider("longitude", longitude)
    consider("region_sc_code", region_sc_code)
    consider("modern_state", modern_state)
    consider("notes", notes)

    if not updates:
        return

    sets = ", ".join([f"{k} = ?" for k in updates.keys()])
    params = tuple(updates.values()) + (place_id,)
    conn.execute(f"UPDATE places SET {sets} WHERE place_id = ?", params)


def load_places(*, db_path: Path, csv_path: Path, dry_run: bool, overwrite: bool) -> None:
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
            row = PlaceRow(
                place_id=_int_or_none(r.get("place_id")),
                place_name=_clean(r.get("place_name")),
                place_type_code=_clean(r.get("place_type_code")),
                parent_place_id=_int_or_none(r.get("parent_place_id")),
                parent_place_name=_none_if_empty(r.get("parent_place_name")),
                parent_place_type_code=_none_if_empty(r.get("parent_place_type_code")),
                latitude=_float_or_none(r.get("latitude")),
                longitude=_float_or_none(r.get("longitude")),
                region_sc_code=_none_if_empty(r.get("region_sc_code")),
                modern_state=_none_if_empty(r.get("modern_state")),
                notes=_none_if_empty(r.get("notes")),
            )

            if not row.place_name or not row.place_type_code:
                raise SystemExit(f"Missing required fields at {csv_path}:{i}")

            # Validate lookup references early for clean failures.
            ok_type = conn.execute(
                "SELECT 1 FROM lkp_place_type WHERE place_type_code = ?",
                (row.place_type_code,),
            ).fetchone()
            if not ok_type:
                raise SystemExit(f"Unknown place_type_code at {csv_path}:{i}: {row.place_type_code!r}")

            if row.region_sc_code:
                ok_region = conn.execute(
                    "SELECT 1 FROM lkp_region_sc WHERE region_sc_code = ?",
                    (row.region_sc_code,),
                ).fetchone()
                if not ok_region:
                    raise SystemExit(f"Unknown region_sc_code at {csv_path}:{i}: {row.region_sc_code!r}")

            parent_id = _resolve_parent_place_id(conn, row)

            # Choose existing row: prefer explicit place_id, else use the natural key.
            place_id: Optional[int] = None
            if row.place_id is not None:
                exists = conn.execute("SELECT 1 FROM places WHERE place_id = ?", (row.place_id,)).fetchone()
                if not exists:
                    raise SystemExit(f"place_id not found at {csv_path}:{i}: {row.place_id}")
                place_id = row.place_id
            else:
                place_id = _place_lookup(
                    conn,
                    place_name=row.place_name,
                    place_type_code=row.place_type_code,
                    parent_place_id=parent_id,
                )

            if place_id is None:
                if dry_run:
                    inserted += 1
                    continue

                cur = conn.execute(
                    """
                    INSERT INTO places (
                      place_name,
                      place_type_code,
                      parent_place_id,
                      latitude,
                      longitude,
                      region_sc_code,
                      modern_state,
                      notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.place_name,
                        row.place_type_code,
                        parent_id,
                        row.latitude,
                        row.longitude,
                        row.region_sc_code,
                        row.modern_state,
                        row.notes,
                    ),
                )
                inserted += 1
                place_id = int(cur.lastrowid)
            else:
                matched_existing += 1

            # Update merge behavior (fill NULLs) or overwrite behavior.
            if place_id is not None:
                before_changes = conn.total_changes
                if not dry_run:
                    _apply_merge_update(
                        conn,
                        place_id=place_id,
                        latitude=row.latitude,
                        longitude=row.longitude,
                        region_sc_code=row.region_sc_code,
                        modern_state=row.modern_state,
                        notes=row.notes,
                        overwrite=overwrite,
                    )
                after_changes = conn.total_changes
                if after_changes > before_changes:
                    updated_existing += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Loaded places staging")
        print(f"  DB: {db_path}")
        print(f"  CSV: {csv_path} ({len(rows)} rows)")
        print("Results")
        print(f"  Inserted: {inserted}{' (dry-run)' if dry_run else ''}")
        print(f"  Matched existing: {matched_existing}")
        print(f"  Updated existing: {updated_existing}")

    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Load places into unionism.db from a staging CSV.")
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument("--csv", default="data/staging/places_staging.csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite non-NULL DB values when the staging row provides a non-NULL value (default is fill-NULLs only).",
    )

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    load_places(
        db_path=(repo_root / args.db).resolve(),
        csv_path=(repo_root / args.csv).resolve(),
        dry_run=bool(args.dry_run),
        overwrite=bool(args.overwrite),
    )


if __name__ == "__main__":
    main()
