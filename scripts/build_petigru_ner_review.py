#!/usr/bin/env python3
"""Generate a triage worksheet for unresolved Petigru NER people rows.

Selects every people row that:
  * was inserted from the Petigru NER load (notes LIKE '%Petigru NER%'), AND
  * is a single-word name (no space), AND
  * has no anchoring data (no positions, no organization links, no residence,
    no correspondence rows).

For each row writes a CSV row with heuristic guesses so a human can mark an
action (keep / drop / merge / rename) and then run apply_petigru_ner_review.py.

CSV columns:
  person_id, full_name, rel_count,
  category_guess,            -- junk | firstname | surname | unmatched
  candidate_canonical_ids,   -- ';'-separated list of other person_ids whose
                                full_name contains this token as a whole word
                                AND that have anchoring data (real people)
  candidate_canonical_names, -- same, names
  action,                    -- LEAVE BLANK; fill with: keep | drop | merge | rename
  merge_target_id,           -- required when action=merge
  rename_to,                 -- required when action=rename
  notes                      -- free text for the reviewer
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "unionism.db"
DEFAULT_OUT = REPO_ROOT / "data" / "staging" / "petigru_ner_review.csv"


# Tokens that are clearly NOT people (common nouns, valedictions, concepts,
# place/event names, OCR artifacts). Lower-cased for comparison.
JUNK_TOKENS = {
    "adieu", "aunt", "uncle", "cousin", "miss", "mister", "mr", "mrs",
    "verdict", "georgians", "carolinians", "yankees", "rebels",
    "apostle", "behold", "blessings", "bench", "ash", "broad",
    "anti-jackson", "bethel", "chickahominy", "chicora", "cap",
    "amen", "alas", "alack", "lord", "god", "heaven", "hell",
    "north", "south", "east", "west",  # only when standalone — beware Jane Petigru NORTH (already merged)
    "court", "house", "senate", "congress", "assembly",
    "providence", "fortune", "fate",
    "boycef",  # OCR artifact of "Boyce"
}

# Common first-name tokens from the mid-19th-century SC/Petigru circle.
# A standalone match here flags the row as a likely-firstname (typically refers
# to a family member, requires manual disambiguation).
FIRSTNAME_TOKENS = {
    "adele", "albert", "alfred", "amos", "andrew", "ann", "anna", "anne",
    "arthur", "austen", "balaam", "bartholomew", "becky", "ben", "benjamin",
    "bill", "brutus", "caroline", "cary", "charles", "charley", "daniel",
    "edward", "eliza", "elizabeth", "fanny", "george", "henry", "james",
    "jane", "john", "kate", "lizzie", "lottie", "lucy", "margaret", "martha",
    "mary", "nancy", "rebecca", "robert", "rose", "sally", "samuel", "susan",
    "thomas", "william",
}


def _clean(s) -> str:
    return ("" if s is None else str(s)).strip()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def fetch_unresolved_rows(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    sql = """
        SELECT p.person_id, p.full_name,
               (SELECT COUNT(*) FROM relationships
                 WHERE person_low_id = p.person_id OR person_high_id = p.person_id) AS rel_count
          FROM people p
         WHERE p.notes LIKE '%Petigru NER%'
           AND p.full_name NOT LIKE '% %'
           AND NOT EXISTS (SELECT 1 FROM positions             WHERE person_id = p.person_id)
           AND NOT EXISTS (SELECT 1 FROM person_organization   WHERE person_id = p.person_id)
           AND NOT EXISTS (SELECT 1 FROM person_place_residence WHERE person_id = p.person_id)
           AND NOT EXISTS (SELECT 1 FROM correspondence
                            WHERE sender_id = p.person_id OR recipient_id = p.person_id)
         ORDER BY p.full_name COLLATE NOCASE
    """
    return list(conn.execute(sql).fetchall())


def find_candidate_canonicals(
    conn: sqlite3.Connection, token: str, exclude_id: int
) -> List[Tuple[int, str]]:
    """Return (person_id, full_name) of other people whose full_name contains
    `token` as a whole word AND that have anchoring data (positions, org links,
    residences, correspondence) OR a multi-word name. This filters out other
    unresolved single-token NER rows from polluting the candidate list."""
    if not token:
        return []
    # Build a whole-word LIKE pattern via SQLite GLOB (case-insensitive via LOWER).
    # We can't easily do regex word boundaries in pure SQLite without extensions,
    # so we LIKE-prefilter then re-check in Python with \b.
    like = f"%{token}%"
    rows = conn.execute(
        """
        SELECT p.person_id, p.full_name
          FROM people p
         WHERE p.person_id != ?
           AND LOWER(p.full_name) LIKE LOWER(?)
           AND (
                p.full_name LIKE '% %'
             OR EXISTS (SELECT 1 FROM positions             WHERE person_id = p.person_id)
             OR EXISTS (SELECT 1 FROM person_organization   WHERE person_id = p.person_id)
             OR EXISTS (SELECT 1 FROM person_place_residence WHERE person_id = p.person_id)
             OR EXISTS (SELECT 1 FROM correspondence
                          WHERE sender_id = p.person_id OR recipient_id = p.person_id)
           )
         ORDER BY p.person_id
        """,
        (exclude_id, like),
    ).fetchall()
    pat = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
    return [(int(r["person_id"]), r["full_name"]) for r in rows if pat.search(r["full_name"])]


def categorize(token: str, candidates: List[Tuple[int, str]]) -> str:
    t = token.lower()
    if t in JUNK_TOKENS:
        return "junk"
    if t in FIRSTNAME_TOKENS:
        return "firstname"
    if candidates:
        return "surname"
    return "unmatched"


def suggested_action(category: str, candidates: List[Tuple[int, str]]) -> Tuple[str, str]:
    """Return (action, merge_target_id) -- we only auto-suggest 'drop' for junk
    and leave everything else blank so the human reviews. Even single-candidate
    surnames are risky to auto-merge (cf. Elliott)."""
    if category == "junk":
        return ("drop", "")
    return ("", "")


def build(conn: sqlite3.Connection, out_path: Path) -> int:
    rows = fetch_unresolved_rows(conn)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "person_id", "full_name", "rel_count",
            "category_guess",
            "candidate_canonical_ids", "candidate_canonical_names",
            "action", "merge_target_id", "rename_to", "notes",
        ])
        for r in rows:
            pid = int(r["person_id"])
            name = _clean(r["full_name"])
            rel_count = int(r["rel_count"])
            candidates = find_candidate_canonicals(conn, name, pid)
            cat = categorize(name, candidates)
            action, merge_target = suggested_action(cat, candidates)
            cand_ids = ";".join(str(cid) for cid, _ in candidates)
            cand_names = ";".join(cn for _, cn in candidates)
            w.writerow([
                pid, name, rel_count, cat, cand_ids, cand_names,
                action, merge_target, "", "",
            ])
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    conn = _connect(args.db)
    try:
        n = build(conn, args.out)
    finally:
        conn.close()
    print(f"Wrote {n} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
