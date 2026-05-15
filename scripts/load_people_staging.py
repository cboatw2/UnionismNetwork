from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


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


@dataclass(frozen=True)
class PeopleRow:
    canonical_key: str
    full_name: Optional[str]
    display_name: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    birth_place_id: Optional[int]
    death_place_id: Optional[int]
    race_code: Optional[str]
    gender: Optional[str]
    class_code: Optional[str]
    occupation: Optional[str]
    home_region_sc_code: Optional[str]
    enslaved_status: Optional[str]
    source_density_code: Optional[str]
    representation_depth_code: Optional[str]
    erasure_flag: int
    erasure_reason_code: Optional[str]
    notes: Optional[str]


@dataclass(frozen=True)
class AliasRow:
    canonical_key: str
    alias_name: str
    source_id: Optional[int]
    notes: Optional[str]


PEOPLE_REQUIRED = {"canonical_key"}
ALIAS_REQUIRED = {"canonical_key", "alias_name"}


def _read_csv(path: Path) -> Tuple[list[str], list[Dict[str, str]]]:
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")
    if path.stat().st_size == 0:
        raise SystemExit(f"CSV is empty (0 bytes): {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames:
            raise SystemExit(f"Could not read header row from: {path}")
        rows: list[Dict[str, str]] = []
        for row in r:
            rows.append({k: (row.get(k) or "") for k in r.fieldnames})
        return list(r.fieldnames), rows


def read_people_rows(path: Path) -> list[PeopleRow]:
    fieldnames, rows = _read_csv(path)
    missing = sorted(PEOPLE_REQUIRED - set(fieldnames))
    if missing:
        raise SystemExit(f"People CSV missing required columns {missing}: {path}")

    out: list[PeopleRow] = []
    for i, r in enumerate(rows, start=2):
        canonical_key = _clean(r.get("canonical_key"))
        if not canonical_key:
            raise SystemExit(f"Empty canonical_key at {path}:{i}")

        out.append(
            PeopleRow(
                canonical_key=canonical_key,
                full_name=_none_if_empty(r.get("full_name")),
                display_name=_none_if_empty(r.get("display_name")),
                birth_year=_int_or_none(r.get("birth_year")),
                death_year=_int_or_none(r.get("death_year")),
                birth_place_id=_int_or_none(r.get("birth_place_id")),
                death_place_id=_int_or_none(r.get("death_place_id")),
                race_code=_none_if_empty(r.get("race_code")),
                gender=_none_if_empty(r.get("gender")),
                class_code=_none_if_empty(r.get("class_code")),
                occupation=_none_if_empty(r.get("occupation")),
                home_region_sc_code=_none_if_empty(r.get("home_region_sc_code")),
                enslaved_status=_none_if_empty(r.get("enslaved_status")),
                source_density_code=_none_if_empty(r.get("source_density_code")),
                representation_depth_code=_none_if_empty(r.get("representation_depth_code")),
                erasure_flag=_bool_int(r.get("erasure_flag"), default=0),
                erasure_reason_code=_none_if_empty(r.get("erasure_reason_code")),
                notes=_none_if_empty(r.get("notes")),
            )
        )

    return out


def read_alias_rows(path: Path) -> list[AliasRow]:
    fieldnames, rows = _read_csv(path)
    missing = sorted(ALIAS_REQUIRED - set(fieldnames))
    if missing:
        raise SystemExit(f"Aliases CSV missing required columns {missing}: {path}")

    out: list[AliasRow] = []
    for i, r in enumerate(rows, start=2):
        canonical_key = _clean(r.get("canonical_key"))
        if not canonical_key:
            raise SystemExit(f"Empty canonical_key at {path}:{i}")
        alias_name = _clean(r.get("alias_name"))
        if not alias_name:
            raise SystemExit(f"Empty alias_name at {path}:{i}")

        out.append(
            AliasRow(
                canonical_key=canonical_key,
                alias_name=alias_name,
                source_id=_int_or_none(r.get("source_id")),
                notes=_none_if_empty(r.get("notes")),
            )
        )

    return out


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    # Minimal sanity checks: tables exist.
    required = {"people", "person_aliases"}
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r[0] for r in rows}
    missing = sorted(required - names)
    if missing:
        raise SystemExit(
            "Database is missing required tables. "
            f"Missing={missing}. Did you run scripts/init_db.py to initialize unionism.db?"
        )


def _norm_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return " ".join(name.strip().split()).lower()


def _find_existing_person_id(conn: sqlite3.Connection, *, full_name: Optional[str], display_name: Optional[str]) -> Optional[int]:
    # Exact-ish match: normalize whitespace/case. We keep this conservative to avoid accidental merges.
    candidates: list[Tuple[str, Optional[str]]] = [("full_name", full_name), ("display_name", display_name)]
    for col, val in candidates:
        n = _norm_name(val)
        if not n:
            continue
        rows = conn.execute(
            f"SELECT person_id FROM people WHERE lower(trim(replace({col}, '  ', ' '))) = ? ORDER BY person_id ASC",
            (n,),
        ).fetchall()
        if not rows:
            continue
        # If multiple, pick the earliest record.
        return int(rows[0][0])
    return None


def _insert_person(conn: sqlite3.Connection, row: PeopleRow) -> int:
    cur = conn.execute(
        """
        INSERT INTO people (
          full_name,
          display_name,
          birth_year,
          death_year,
          birth_place_id,
          death_place_id,
          race_code,
          gender,
          class_code,
          occupation,
          home_region_sc_code,
          enslaved_status,
          source_density_code,
          representation_depth_code,
          erasure_flag,
          erasure_reason_code,
          notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.full_name,
            row.display_name,
            row.birth_year,
            row.death_year,
            row.birth_place_id,
            row.death_place_id,
            row.race_code,
            row.gender,
            row.class_code,
            row.occupation,
            row.home_region_sc_code,
            row.enslaved_status,
            row.source_density_code,
            row.representation_depth_code,
            row.erasure_flag,
            row.erasure_reason_code,
            row.notes,
        ),
    )
    return int(cur.lastrowid)


def _insert_alias(conn: sqlite3.Connection, *, person_id: int, alias: AliasRow) -> bool:
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO person_aliases (person_id, alias_name, source_id, notes)
        VALUES (?, ?, ?, ?)
        """,
        (person_id, alias.alias_name, alias.source_id, alias.notes),
    )
    return cur.rowcount == 1


def load(
    *,
    db_path: Path,
    people_csv: Path,
    aliases_csv: Path,
    match_existing: bool,
    dry_run: bool,
) -> None:
    people_rows = read_people_rows(people_csv)
    alias_rows = read_alias_rows(aliases_csv)

    conn = _connect(db_path)
    try:
        _ensure_schema(conn)

        # Map canonical_key -> person_id
        mapping: Dict[str, int] = {}

        inserted_people = 0
        matched_people = 0

        conn.execute("BEGIN")
        for p in people_rows:
            if p.canonical_key in mapping:
                raise SystemExit(f"Duplicate canonical_key in people CSV: {p.canonical_key}")

            person_id: Optional[int] = None
            if match_existing:
                person_id = _find_existing_person_id(conn, full_name=p.full_name, display_name=p.display_name)

            if person_id is not None:
                mapping[p.canonical_key] = person_id
                matched_people += 1
                continue

            if dry_run:
                # Use a sentinel negative ID to keep mapping shape; aliases will be skipped.
                mapping[p.canonical_key] = -1
                inserted_people += 1
                continue

            new_id = _insert_person(conn, p)
            mapping[p.canonical_key] = new_id
            inserted_people += 1

        inserted_aliases = 0
        skipped_aliases = 0
        missing_keys: set[str] = set()

        for a in alias_rows:
            pid = mapping.get(a.canonical_key)
            if pid is None:
                missing_keys.add(a.canonical_key)
                continue
            if dry_run:
                continue
            if pid < 0:
                # Would-be inserted person; skip alias in dry-run behavior.
                continue

            ok = _insert_alias(conn, person_id=pid, alias=a)
            if ok:
                inserted_aliases += 1
            else:
                skipped_aliases += 1

        if missing_keys:
            raise SystemExit(
                "Aliases CSV contains canonical_key values not present in people CSV: "
                + ", ".join(sorted(missing_keys)[:25])
                + (" ..." if len(missing_keys) > 25 else "")
            )

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Loaded staging CSVs")
        print(f"  DB: {db_path}")
        print(f"  People CSV: {people_csv} ({len(people_rows)} rows)")
        print(f"  Aliases CSV: {aliases_csv} ({len(alias_rows)} rows)")
        print("Results")
        print(f"  People: inserted={inserted_people} matched_existing={matched_people}")
        if dry_run:
            print("  Aliases: dry-run (not applied)")
        else:
            print(f"  Aliases: inserted={inserted_aliases} skipped_existing={skipped_aliases}")
            # Final counts for quick confidence.
            pcount = conn.execute("SELECT count(*) FROM people").fetchone()[0]
            acount = conn.execute("SELECT count(*) FROM person_aliases").fetchone()[0]
            print(f"  DB totals: people={pcount} aliases={acount}")

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Load unionism_people_staging.csv and unionism_aliases_staging.csv into unionism.db. "
            "This script maps canonical_key -> person_id as it inserts, and then inserts aliases."
        )
    )
    parser.add_argument(
        "--db",
        default="unionism.db",
        help="SQLite database path (default: unionism.db in repo root)",
    )
    parser.add_argument(
        "--people-csv",
        default="data/staging/unionism_people_staging.csv",
        help="Path to people staging CSV",
    )
    parser.add_argument(
        "--aliases-csv",
        default="data/staging/unionism_aliases_staging.csv",
        help="Path to aliases staging CSV",
    )
    parser.add_argument(
        "--no-match-existing",
        action="store_true",
        help="Do not attempt to match existing people rows by name; always insert new people",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report counts but do not modify the DB",
    )

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    load(
        db_path=(repo_root / args.db).resolve(),
        people_csv=(repo_root / args.people_csv).resolve(),
        aliases_csv=(repo_root / args.aliases_csv).resolve(),
        match_existing=not args.no_match_existing,
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    main()
