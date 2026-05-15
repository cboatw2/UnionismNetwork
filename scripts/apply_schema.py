from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Apply schema.sql to an existing SQLite DB (idempotent). "
            "This is mainly used to add new indexes/triggers as the schema evolves."
        )
    )
    p.add_argument("--db", default="unionism.db", help="SQLite DB path (relative to repo root)")
    p.add_argument("--schema", default="schema.sql", help="Schema SQL path (relative to repo root)")
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
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Applied schema to {db_path}")


if __name__ == "__main__":
    main()
