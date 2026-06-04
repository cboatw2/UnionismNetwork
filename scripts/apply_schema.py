from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable


# Additive column additions tracked by apply_schema. SQLite has no
# ALTER TABLE ADD COLUMN IF NOT EXISTS, so we introspect PRAGMA table_info
# and only add what's missing. Foreign-key REFERENCES clauses are accepted
# by ALTER TABLE ADD COLUMN in SQLite even though they are not strictly
# enforced retroactively; that matches our Phase 1 intent (additive only,
# legacy columns still authoritative).
ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    # (table, column, full ALTER ADD spec)
    ("positions", "stance_code",
     "stance_code TEXT REFERENCES lkp_stance(stance_code)"),
    ("positions", "position_notes",
     "position_notes TEXT"),
    ("relationship_characterizations", "stance_code",
     "stance_code TEXT REFERENCES lkp_stance(stance_code)"),
    ("relationship_characterizations", "relchar_notes",
     "relchar_notes TEXT"),
]


def existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def apply_additive_columns(conn: sqlite3.Connection,
                           additions: Iterable[tuple[str, str, str]]) -> list[str]:
    applied: list[str] = []
    for table, column, spec in additions:
        # If the table doesn't exist yet, schema.sql's CREATE TABLE IF NOT EXISTS
        # will already include the column for fresh DBs; nothing to do here.
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if cur.fetchone() is None:
            continue
        if column in existing_columns(conn, table):
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {spec}")
        applied.append(f"{table}.{column}")
    return applied


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Apply schema.sql to an existing SQLite DB (idempotent). "
            "Creates new tables/indexes/triggers, seeds lookup vocabularies, "
            "and ALTERs in any additive columns the canonical schema has gained."
        )
    )
    p.add_argument("--db", default="unionism.db",
                   help="SQLite DB path (relative to repo root)")
    p.add_argument("--schema", default="schema.sql",
                   help="Schema SQL path (relative to repo root)")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve()
    schema_path = (repo_root / args.schema).resolve()

    if not db_path.exists() or db_path.stat().st_size == 0:
        raise SystemExit(f"DB not found or empty: {db_path}")
    if not schema_path.exists() or schema_path.stat().st_size == 0:
        raise SystemExit(f"Schema not found or empty: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        # Order matters: add missing columns first, otherwise indexes/seeds in
        # schema.sql that reference the new columns will fail on existing DBs
        # (CREATE TABLE IF NOT EXISTS is a no-op for tables that already exist,
        # so it never adds the new columns to them).
        applied = apply_additive_columns(conn, ADDITIVE_COLUMNS)
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Applied schema to {db_path}")
    if applied:
        print(f"Added columns: {', '.join(applied)}")
    else:
        print("No additive columns needed.")


if __name__ == "__main__":
    main()
