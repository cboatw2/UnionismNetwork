from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema_path = repo_root / "schema.sql"
    seed_path = repo_root / "seed_minimal.sql"
    db_path = repo_root / "unionism.db"

    if not schema_path.exists():
        raise SystemExit(f"Missing {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")
    seed_sql = seed_path.read_text(encoding="utf-8") if seed_path.exists() else ""

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
