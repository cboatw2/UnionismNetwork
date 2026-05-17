"""Reusable people-merge helper.

Usage:
    python scripts/merge_people.py <survivor_id> <loser_id> [<loser_id> ...] [--note "..."]

For each loser:
  - person_aliases rows repointed to survivor (UPDATE OR IGNORE) then leftovers deleted.
  - Survivor gains the loser's full_name as an alias if not already present.
  - relationships are normalized so person_low_id < person_high_id with survivor in place
    of loser; self-loops with survivor and UNIQUE-collision rows are deleted.
  - relationship_characterizations follow relationships via FK (no change needed).
  - positions, person_organization, person_place_residence, correspondence are repointed.
  - Survivor's notes get an audit suffix.
  - Loser row deleted.

Wrapped in a single transaction.
"""
from __future__ import annotations
import argparse
import datetime as _dt
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "unionism.db"


def merge(con: sqlite3.Connection, survivor: int, losers: list[int], note: str | None) -> None:
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")

    # Sanity
    rows = cur.execute(
        f"SELECT person_id, full_name FROM people WHERE person_id IN ({','.join(['?']*(len(losers)+1))})",
        [survivor, *losers],
    ).fetchall()
    found = {r[0]: r[1] for r in rows}
    if survivor not in found:
        raise SystemExit(f"Survivor id {survivor} not found")
    missing = [pid for pid in losers if pid not in found]
    if missing:
        raise SystemExit(f"Loser id(s) not found: {missing}")

    placeholders = ",".join(["?"] * len(losers))

    # 1. Add each loser's full_name as an alias on the survivor (if distinct).
    for lid in losers:
        cur.execute(
            "INSERT OR IGNORE INTO person_aliases (person_id, alias_name) VALUES (?, ?)",
            (survivor, found[lid]),
        )

    # 2. Repoint aliases; drop leftovers.
    cur.execute(
        f"UPDATE OR IGNORE person_aliases SET person_id = ? WHERE person_id IN ({placeholders})",
        (survivor, *losers),
    )
    cur.execute(
        f"DELETE FROM person_aliases WHERE person_id IN ({placeholders})",
        losers,
    )

    # 3. Relationships -- normalize low<high with survivor.
    # Drop any rel that would become a self-loop.
    cur.execute(
        f"""DELETE FROM relationships
            WHERE (person_low_id  IN ({placeholders}) AND person_high_id = ?)
               OR (person_high_id IN ({placeholders}) AND person_low_id  = ?)""",
        (*losers, survivor, *losers, survivor),
    )
    # Loser on low side, partner > survivor: just bump low to survivor.
    cur.execute(
        f"""UPDATE OR IGNORE relationships SET person_low_id = ?
            WHERE person_low_id IN ({placeholders}) AND person_high_id > ?""",
        (survivor, *losers, survivor),
    )
    # Loser on low side, partner < survivor: swap.
    cur.execute(
        f"""UPDATE OR IGNORE relationships
            SET person_low_id = person_high_id, person_high_id = ?
            WHERE person_low_id IN ({placeholders}) AND person_high_id < ?""",
        (survivor, *losers, survivor),
    )
    # Loser on high side, partner < survivor: bump high to survivor.
    cur.execute(
        f"""UPDATE OR IGNORE relationships SET person_high_id = ?
            WHERE person_high_id IN ({placeholders}) AND person_low_id < ?""",
        (survivor, *losers, survivor),
    )
    # Loser on high side, partner > survivor: swap.
    cur.execute(
        f"""UPDATE OR IGNORE relationships
            SET person_high_id = person_low_id, person_low_id = ?
            WHERE person_high_id IN ({placeholders}) AND person_low_id > ?""",
        (survivor, *losers, survivor),
    )
    # Drop any leftover loser refs (UNIQUE collisions).
    cur.execute(
        f"""DELETE FROM relationships
            WHERE person_low_id IN ({placeholders}) OR person_high_id IN ({placeholders})""",
        (*losers, *losers),
    )

    # 4. Single-FK tables.
    for tbl in (
        "positions",
        "person_organization",
        "person_place_residence",
    ):
        cur.execute(
            f"UPDATE OR IGNORE {tbl} SET person_id = ? WHERE person_id IN ({placeholders})",
            (survivor, *losers),
        )
        cur.execute(
            f"DELETE FROM {tbl} WHERE person_id IN ({placeholders})",
            losers,
        )

    # 5. Correspondence has sender_id and recipient_id.
    cur.execute(
        f"UPDATE OR IGNORE correspondence SET sender_id = ? WHERE sender_id IN ({placeholders})",
        (survivor, *losers),
    )
    cur.execute(
        f"UPDATE OR IGNORE correspondence SET recipient_id = ? WHERE recipient_id IN ({placeholders})",
        (survivor, *losers),
    )
    cur.execute(
        f"""DELETE FROM correspondence
            WHERE sender_id IN ({placeholders}) OR recipient_id IN ({placeholders})""",
        (*losers, *losers),
    )

    # 6. Audit note on survivor.
    today = _dt.date.today().isoformat()
    audit = f" | merged from ids {', '.join(str(x) for x in losers)} on {today}"
    if note:
        audit += f": {note}"
    cur.execute(
        "UPDATE people SET notes = TRIM(COALESCE(notes,'') || ?) WHERE person_id = ?",
        (audit, survivor),
    )

    # 7. Delete loser people.
    cur.execute(
        f"DELETE FROM people WHERE person_id IN ({placeholders})",
        losers,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge people rows.")
    ap.add_argument("survivor", type=int)
    ap.add_argument("losers", type=int, nargs="+")
    ap.add_argument("--note", type=str, default=None)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        with con:
            merge(con, args.survivor, args.losers, args.note)
    finally:
        # Quick verify
        row = con.execute(
            "SELECT person_id, full_name, display_name, occupation FROM people WHERE person_id = ?",
            (args.survivor,),
        ).fetchone()
        rels = con.execute(
            "SELECT COUNT(*) FROM relationships WHERE person_low_id = ? OR person_high_id = ?",
            (args.survivor, args.survivor),
        ).fetchone()[0]
        aliases = [
            r[0]
            for r in con.execute(
                "SELECT alias_name FROM person_aliases WHERE person_id = ? ORDER BY alias_name",
                (args.survivor,),
            ).fetchall()
        ]
        print(f"Survivor: {row}")
        print(f"Relationships: {rels}")
        print(f"Aliases ({len(aliases)}): {aliases}")
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
