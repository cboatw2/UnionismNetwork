from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def normalize_name(name: str) -> str:
    # Keep in sync with PerryLetters/BFPerry_Letters_Database/PeopleExtractionForUnionismNetwork.py
    import re

    n = (name or "").strip().lower()
    n = n.replace("’", "'")
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"[^\w\s']", "", n)
    return n.strip()


def canonical_key_from_name(name: str) -> str:
    n = normalize_name(name)
    n = n.replace(" ", "_")
    return n or "unknown"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_lookup_relationship_type(conn: sqlite3.Connection, code: str, label: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO lkp_relationship_type (relationship_type_code, label) VALUES (?, ?)",
        (code, label),
    )


def _get_or_create_source(
    conn: sqlite3.Connection,
    *,
    source_type_code: str,
    title: str,
    creator: Optional[str],
    date_created: Optional[str],
    citation_full: Optional[str],
    notes: Optional[str],
) -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_type_code = ? AND title = ? ORDER BY source_id ASC LIMIT 1",
        (source_type_code, title),
    ).fetchone()
    if row:
        return int(row[0])

    cur = conn.execute(
        """
        INSERT INTO sources (
          source_type_code,
          title,
          creator,
          date_created,
          citation_full,
          notes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_type_code, title, creator, date_created, citation_full, notes),
    )
    return int(cur.lastrowid)


def _strength_from_count(n: int) -> int:
    # Relationship strength is 1–3.
    if n <= 1:
        return 1
    if n <= 3:
        return 2
    return 3


def _read_unionism_people_staging(path: Path) -> list[Tuple[str, str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty people staging CSV: {path}")

    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        required = {"canonical_key", "full_name", "display_name"}
        if not r.fieldnames or any(c not in r.fieldnames for c in required):
            raise SystemExit(f"People staging CSV missing required columns {sorted(required)}: {path}")

        out: list[Tuple[str, str, str]] = []
        for i, row in enumerate(r, start=2):
            key = _clean(row.get("canonical_key"))
            if not key:
                raise SystemExit(f"Empty canonical_key at {path}:{i}")
            out.append((key, _clean(row.get("full_name")), _clean(row.get("display_name"))))
        return out


def _resolve_person_id_by_name(conn: sqlite3.Connection, *, full_name: str, display_name: str) -> Optional[int]:
    # Conservative exact matching.
    for val in (display_name, full_name):
        v = _clean(val)
        if not v:
            continue
        rows = conn.execute(
            "SELECT person_id FROM people WHERE full_name = ? OR display_name = ? ORDER BY person_id ASC",
            (v, v),
        ).fetchall()
        if len(rows) == 1:
            return int(rows[0][0])
        if len(rows) > 1:
            # Prefer the row that came from people_review if available.
            pref = conn.execute(
                """
                SELECT person_id
                FROM people
                WHERE (full_name = ? OR display_name = ?)
                  AND notes LIKE 'From people_review%'
                ORDER BY person_id ASC
                """,
                (v, v),
            ).fetchall()
            if len(pref) == 1:
                return int(pref[0][0])
            raise SystemExit(f"Ambiguous name match for {v!r} in unionism.db ({len(rows)} rows)")
    return None


def _load_key_to_unionism_id(unionism_db: Path, staging_csv: Path) -> Dict[str, int]:
    staged = _read_unionism_people_staging(staging_csv)
    conn = _connect(unionism_db)
    try:
        mapping: Dict[str, int] = {}
        missing: list[str] = []
        for key, full_name, display_name in staged:
            pid = _resolve_person_id_by_name(conn, full_name=full_name, display_name=display_name)
            if pid is None:
                missing.append(key)
                continue
            mapping[key] = pid

        if missing:
            raise SystemExit(
                "Could not resolve some canonical_key rows to a unique person_id in unionism.db. "
                f"First few: {missing[:10]}"
            )

        return mapping
    finally:
        conn.close()


def _load_perry_people(perry_db: Path) -> Dict[int, str]:
    conn = _connect(perry_db)
    try:
        rows = conn.execute("SELECT person_id, name FROM people").fetchall()
        return {int(r[0]): _clean(r[1]) for r in rows}
    finally:
        conn.close()


def _iter_letter_participants(perry_db: Path) -> Iterable[Tuple[int, Set[int]]]:
    conn = _connect(perry_db)
    try:
        letter_rows = conn.execute("SELECT id, sender_id, recipient_id FROM letter").fetchall()
        # Preload mentions grouped by letter_id.
        mentions = conn.execute("SELECT letter_id, person_id FROM mentioned_people").fetchall()
        by_letter: Dict[int, Set[int]] = {}
        for r in mentions:
            lid = int(r[0])
            pid = int(r[1])
            by_letter.setdefault(lid, set()).add(pid)

        for lr in letter_rows:
            lid = int(lr[0])
            participants = set(by_letter.get(lid, set()))
            sender_id = lr[1]
            recipient_id = lr[2]
            if sender_id is not None:
                participants.add(int(sender_id))
            if recipient_id is not None:
                participants.add(int(recipient_id))
            yield lid, participants
    finally:
        conn.close()


@dataclass(frozen=True)
class CoMentionResult:
    unique_pairs: int
    inserted: int
    skipped_existing: int
    dropped_low_count: int


def link_co_mentions(
    *,
    unionism_db: Path,
    perry_db: Path,
    unionism_people_staging_csv: Path,
    anchor_person_id: int,
    exclude_anchor: bool,
    relationship_type_code: str,
    relationship_type_label: str,
    source_type_code: str,
    source_title: str,
    source_creator: Optional[str],
    source_date_created: Optional[str],
    source_citation_full: Optional[str],
    source_notes: Optional[str],
    start_date: str,
    end_date: str,
    min_count: int,
    dry_run: bool,
) -> CoMentionResult:
    key_to_unionism_id = _load_key_to_unionism_id(unionism_db, unionism_people_staging_csv)
    allowed_keys = set(key_to_unionism_id.keys())

    perry_people = _load_perry_people(perry_db)

    # Compute anchor canonical key from unionism DB name.
    conn_u = _connect(unionism_db)
    try:
        anchor_row = conn_u.execute(
            "SELECT full_name, display_name FROM people WHERE person_id = ?",
            (anchor_person_id,),
        ).fetchone()
        if not anchor_row:
            raise SystemExit(f"Anchor person_id not found in unionism.db: {anchor_person_id}")
        anchor_name = _clean(anchor_row[1]) or _clean(anchor_row[0])
    finally:
        conn_u.close()

    anchor_key = canonical_key_from_name(anchor_name)

    pair_counts: Counter[Tuple[int, int]] = Counter()

    for _lid, participant_ids in _iter_letter_participants(perry_db):
        keys: Set[str] = set()
        for pid in participant_ids:
            nm = perry_people.get(pid)
            if not nm:
                continue
            key = canonical_key_from_name(nm)
            if key in allowed_keys:
                keys.add(key)

        if exclude_anchor:
            keys.discard(anchor_key)

        ids = sorted({key_to_unionism_id[k] for k in keys if k in key_to_unionism_id})
        if len(ids) < 2:
            continue

        # Add all unordered pairs.
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pair_counts[(ids[i], ids[j])] += 1

    # Insert aggregated edges.
    conn = _connect(unionism_db)
    try:
        conn.execute("BEGIN")
        _ensure_lookup_relationship_type(conn, relationship_type_code, relationship_type_label)
        source_id = _get_or_create_source(
            conn,
            source_type_code=source_type_code,
            title=source_title,
            creator=source_creator,
            date_created=source_date_created,
            citation_full=source_citation_full,
            notes=source_notes,
        )

        inserted = 0
        skipped = 0
        dropped_low = 0

        for (low_id, high_id), cnt in pair_counts.items():
            if cnt < min_count:
                dropped_low += 1
                continue

            strength = _strength_from_count(cnt)
            notes = (
                f"Co-mentioned in BF Perry letters (aggregated). "
                f"co_mention_letters_count={cnt}; min_count={min_count}; "
                f"inputs=mentioned_people+sender+recipient; exclude_anchor={int(exclude_anchor)}"
            )

            if dry_run:
                inserted += 1
                continue

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO relationships (
                  person_low_id,
                  person_high_id,
                  relationship_type_code,
                  start_date,
                  end_date,
                  strength,
                  source_id,
                  notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (low_id, high_id, relationship_type_code, start_date, end_date, strength, source_id, notes),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

        print("Built co-mention edges")
        print(f"  unionism.db: {unionism_db}")
        print(f"  perry db: {perry_db}")
        print(f"  relationship_type: {relationship_type_code}")
        print(f"  source: {source_id} ({source_title})")
        print("Counts")
        print(f"  Unique pairs (raw): {len(pair_counts)}")
        print(f"  Dropped (count < {min_count}): {dropped_low}")
        print(f"  Inserted: {inserted}{' (dry-run)' if dry_run else ''}")
        print(f"  Skipped existing: {skipped}")

        return CoMentionResult(
            unique_pairs=len(pair_counts),
            inserted=inserted,
            skipped_existing=skipped,
            dropped_low_count=dropped_low,
        )
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Generate 'mentioned with' co-mention edges from PerryLetters/BFPerryLetters.db and insert them into "
            "UnionismNetwork unionism.db as aggregated relationships."
        )
    )
    ap.add_argument("--unionism-db", default="unionism.db")
    ap.add_argument("--perry-db", default="../PerryLetters/BFPerryLetters.db")
    ap.add_argument("--people-staging-csv", default="data/staging/unionism_people_staging.csv")
    ap.add_argument("--anchor-person-id", type=int, default=2, help="BF Perry person_id in unionism.db")
    ap.add_argument("--include-anchor", action="store_true", help="Include anchor in co-mention pairs")
    ap.add_argument("--relationship-type-code", default="corpus_co_mention")
    ap.add_argument("--relationship-type-label", default="Co-mentioned in corpus unit")
    ap.add_argument("--source-type-code", default="letter")
    ap.add_argument("--source-title", default="B. F. Perry letters (co-mentions aggregated)")
    ap.add_argument("--source-creator", default="NER extraction pipeline")
    ap.add_argument("--source-date-created", default=None)
    ap.add_argument(
        "--source-citation-full",
        default="Co-mention edges aggregated from B. F. Perry letters corpus (placeholder citation; replace with archival citation).",
    )
    ap.add_argument(
        "--source-notes",
        default="Auto-generated co-mention edges: two people appear in the same letter (mentioned_people + sender/recipient). Not a claim of direct relationship.",
    )
    ap.add_argument("--start-date", default="1817-01-01")
    ap.add_argument("--end-date", default="1865-12-31")
    ap.add_argument("--min-count", type=int, default=1, help="Minimum letters co-mentioned to create an edge")
    ap.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    link_co_mentions(
        unionism_db=(repo_root / args.unionism_db).resolve(),
        perry_db=(repo_root / args.perry_db).resolve(),
        unionism_people_staging_csv=(repo_root / args.people_staging_csv).resolve(),
        anchor_person_id=int(args.anchor_person_id),
        exclude_anchor=not bool(args.include_anchor),
        relationship_type_code=args.relationship_type_code,
        relationship_type_label=args.relationship_type_label,
        source_type_code=args.source_type_code,
        source_title=args.source_title,
        source_creator=args.source_creator,
        source_date_created=args.source_date_created,
        source_citation_full=args.source_citation_full,
        source_notes=args.source_notes,
        start_date=args.start_date,
        end_date=args.end_date,
        min_count=max(1, int(args.min_count)),
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    main()
