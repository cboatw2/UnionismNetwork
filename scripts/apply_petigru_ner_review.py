#!/usr/bin/env python3
"""Apply manual review decisions for unresolved Petigru NER people rows.

Reads data/staging/petigru_ner_review.csv (produced by
build_petigru_ner_review.py and edited by hand) and applies the marked actions
in a single transaction.

Supported actions (case-insensitive, whitespace-trimmed):

  keep         -- no-op; row stays as-is.
  drop         -- DELETE the people row; ON DELETE CASCADE removes its
                  relationships, aliases, etc.
  merge        -- Merge this person_id into merge_target_id using the existing
                  scripts.merge_people helper (re-normalizes rel endpoints,
                  preserves aliases, drops self-loops, etc.).
  rename       -- UPDATE full_name/display_name to rename_to (no merge).
  (blank or 'review') -- skipped.

Usage:
  python scripts/apply_petigru_ner_review.py \
      [--csv data/staging/petigru_ner_review.csv] \
      [--db unionism.db] \
      [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from merge_people import merge as merge_people_fn  # type: ignore  # noqa: E402

DEFAULT_DB = REPO_ROOT / "unionism.db"
DEFAULT_CSV = REPO_ROOT / "data" / "staging" / "petigru_ner_review.csv"

VALID_ACTIONS = {"", "review", "keep", "drop", "merge", "rename"}


def _clean(s) -> str:
    return ("" if s is None else str(s)).strip()


def _to_int(s, *, field: str, row_num: int) -> int:
    s = _clean(s)
    if not s:
        raise SystemExit(f"row {row_num}: {field} is required and empty")
    try:
        return int(s)
    except ValueError as e:
        raise SystemExit(f"row {row_num}: {field}={s!r} is not an int") from e


def read_decisions(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"Review CSV not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        required = {"person_id", "full_name", "action"}
        missing = required - set(r.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing required columns: {sorted(missing)}")
        return [dict(row) for row in r]


def apply_all(conn: sqlite3.Connection, decisions: List[Dict[str, str]], *, dry_run: bool) -> Dict[str, int]:
    stats = {"keep": 0, "drop": 0, "merge": 0, "rename": 0, "skipped": 0, "errors": 0}
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")

    for i, row in enumerate(decisions, start=2):  # +1 for header
        action = _clean(row.get("action")).lower()
        if action not in VALID_ACTIONS:
            stats["errors"] += 1
            print(f"row {i}: unknown action {action!r} -- skipped", file=sys.stderr)
            continue
        if action in ("", "review", "keep"):
            stats[action if action in stats else "skipped"] += 1 if action == "keep" else 0
            if action in ("", "review"):
                stats["skipped"] += 1
            continue

        pid = _to_int(row.get("person_id"), field="person_id", row_num=i)
        name = _clean(row.get("full_name"))

        # Verify the row still exists and still has its original name.
        cur_row = cur.execute(
            "SELECT full_name FROM people WHERE person_id = ?", (pid,)
        ).fetchone()
        if cur_row is None:
            print(f"row {i}: person_id {pid} ({name!r}) no longer exists -- skipped", file=sys.stderr)
            stats["skipped"] += 1
            continue
        if name and cur_row[0] != name:
            print(
                f"row {i}: person_id {pid} now named {cur_row[0]!r}, CSV says {name!r} -- skipped for safety",
                file=sys.stderr,
            )
            stats["skipped"] += 1
            continue

        if action == "drop":
            if not dry_run:
                cur.execute("DELETE FROM people WHERE person_id = ?", (pid,))
            stats["drop"] += 1
        elif action == "rename":
            new_name = _clean(row.get("rename_to"))
            if not new_name:
                raise SystemExit(f"row {i}: action=rename requires rename_to")
            if not dry_run:
                cur.execute(
                    "UPDATE people SET full_name = ?, display_name = ? WHERE person_id = ?",
                    (new_name, new_name, pid),
                )
            stats["rename"] += 1
        elif action == "merge":
            target = _to_int(row.get("merge_target_id"), field="merge_target_id", row_num=i)
            if target == pid:
                raise SystemExit(f"row {i}: merge_target_id == person_id ({pid}); cannot self-merge")
            if not dry_run:
                merge_people_fn(conn, target, [pid], note=f"petigru_ner_review row {i}")
            stats["merge"] += 1

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    decisions = read_decisions(args.csv)
    print(f"Loaded {len(decisions)} decisions from {args.csv}")

    conn = sqlite3.connect(str(args.db))
    try:
        with conn:  # single transaction
            stats = apply_all(conn, decisions, dry_run=args.dry_run)
    finally:
        conn.close()

    label = "DRY-RUN " if args.dry_run else ""
    print(
        f"{label}done. keep={stats['keep']} drop={stats['drop']} "
        f"merge={stats['merge']} rename={stats['rename']} "
        f"skipped={stats['skipped']} errors={stats['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
