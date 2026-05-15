from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="Initialize a new unionism.db from schema.sql (+ optional seed SQL).")
    p.add_argument("--db", default="unionism.db", help="SQLite DB path (relative to repo root)")
    p.add_argument("--schema", default="schema.sql", help="Schema SQL path (relative to repo root)")
    p.add_argument(
        "--seed",
        default="seed_minimal.sql",
        help="Optional seed SQL path (relative to repo root). Use '' to skip.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete an existing DB at --db before initializing.",
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    schema_path = (repo_root / args.schema).resolve()
    db_path = (repo_root / args.db).resolve()
    seed_path = (repo_root / args.seed).resolve() if args.seed else None

    if not schema_path.exists():
        raise SystemExit(f"Missing schema: {schema_path}")

    if db_path.exists() and db_path.stat().st_size > 0:
        if not args.overwrite:
            raise SystemExit(
                f"Refusing to initialize over existing DB: {db_path}\n"
                "Use --overwrite to delete and rebuild, or run scripts/apply_schema.py to apply new indexes/triggers."
            )
        db_path.unlink()

    schema_sql = schema_path.read_text(encoding="utf-8")
    seed_sql = ""
    if seed_path and seed_path.exists() and seed_path.stat().st_size > 0:
        seed_sql = seed_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        if seed_sql.strip():
            conn.executescript(seed_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Initialized {db_path}")


if __name__ == "__main__":
    main()
