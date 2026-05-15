#!/usr/bin/env python3
"""Load Petigru NER entities into unionism.db.

Mirrors the Perry corpus workflow but tags every row with two new Petigru
`sources` entries so corpus provenance is preserved (Option A):

  - "James L. Petigru letters (corpus)"          → person_aliases.source_id
  - "James L. Petigru letters (co-mentions aggregated)" → relationships.source_id

Inputs:
  - Petigru_NER_entities.csv with columns: letter_number, entity_name, entity_type
    (PERSON or LOCATION; produced by Petigru/ner_letters_folder.py)

Behavior:
  - PERSON entities: canonicalize, match against people.full_name/display_name and
    existing person_aliases.alias_name. If no match, insert a new people row.
    Always insert a person_aliases row tagged with the Petigru corpus source.
  - Co-mentions: per letter, take the set of resolved person_ids, build pairs,
    aggregate counts, insert into relationships (type "co_mentioned") at or above
    --min-co-mentions.
  - LOCATION entities: written to a review CSV for manual curation before any
    insert into places (which requires place_type_code).

Usage:
  python scripts/load_petigru_ner.py \
      --db unionism.db \
      --csv /Users/crboatwright/Petigru/Petigru_NER_entities.csv \
      --locations-review-csv data/staging/petigru_ner_locations_review.csv \
      --min-co-mentions 2 \
      --dry-run
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Helpers (kept in sync with link_co_mentions_from_perryletters.py)
# ---------------------------------------------------------------------------

def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def normalize_name(name: str) -> str:
    n = (name or "").strip().lower()
    n = n.replace("\u2019", "'")
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
    notes: Optional[str],
) -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_type_code = ? AND title = ? ORDER BY source_id ASC LIMIT 1",
        (source_type_code, title),
    ).fetchone()
    if row:
        return int(row[0])

    cur = conn.execute(
        "INSERT INTO sources (source_type_code, title, creator, notes) VALUES (?, ?, ?, ?)",
        (source_type_code, title, creator, notes),
    )
    return int(cur.lastrowid)


def _strength_from_count(n: int) -> int:
    if n <= 1:
        return 1
    if n <= 3:
        return 2
    return 3


# ---------------------------------------------------------------------------
# Person matching index
# ---------------------------------------------------------------------------

@dataclass
class PersonIndex:
    """In-memory index from canonical_key -> person_id."""

    key_to_id: Dict[str, int]

    def lookup(self, raw_name: str) -> Optional[int]:
        key = canonical_key_from_name(raw_name)
        return self.key_to_id.get(key)


def _build_person_index(conn: sqlite3.Connection) -> PersonIndex:
    """Index people + aliases by canonical_key for fuzzy-but-deterministic matching."""
    key_to_id: Dict[str, int] = {}
    ambiguous: Dict[str, Set[int]] = defaultdict(set)

    def consider(name: Optional[str], pid: int) -> None:
        v = _clean(name or "")
        if not v:
            return
        key = canonical_key_from_name(v)
        if not key or key == "unknown":
            return
        existing = key_to_id.get(key)
        if existing is None:
            key_to_id[key] = pid
        elif existing != pid:
            ambiguous[key].update({existing, pid})

    for r in conn.execute("SELECT person_id, full_name, display_name FROM people").fetchall():
        pid = int(r["person_id"])
        consider(r["full_name"], pid)
        consider(r["display_name"], pid)

    for r in conn.execute("SELECT person_id, alias_name FROM person_aliases").fetchall():
        consider(r["alias_name"], int(r["person_id"]))

    # Drop ambiguous keys so we don't merge unrelated people on weak matches.
    for k in ambiguous:
        key_to_id.pop(k, None)

    return PersonIndex(key_to_id=key_to_id)


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------

REQUIRED_COLS = {"letter_number", "entity_name", "entity_type"}


@dataclass(frozen=True)
class NerRow:
    letter_number: str
    entity_name: str
    entity_type: str


def _read_csv(path: Path) -> List[NerRow]:
    if not path.exists() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty CSV: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or not REQUIRED_COLS.issubset(set(r.fieldnames)):
            raise SystemExit(
                f"CSV missing required columns {sorted(REQUIRED_COLS)}: {path}"
            )
        out: List[NerRow] = []
        for row in r:
            ent_type = _clean(row.get("entity_type")).upper()
            ent_name = _clean(row.get("entity_name"))
            if not ent_name or ent_type not in {"PERSON", "LOCATION"}:
                continue
            out.append(
                NerRow(
                    letter_number=_clean(row.get("letter_number")),
                    entity_name=ent_name,
                    entity_type=ent_type,
                )
            )
        return out


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

@dataclass
class LoadStats:
    people_inserted: int = 0
    aliases_inserted: int = 0
    aliases_skipped_existing: int = 0
    co_mention_pairs_considered: int = 0
    co_mention_pairs_kept: int = 0
    relationships_inserted: int = 0
    relationships_skipped_existing: int = 0
    location_unique: int = 0


def _insert_person(conn: sqlite3.Connection, *, name: str, note: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO people (full_name, display_name, notes)
        VALUES (?, ?, ?)
        """,
        (name, name, note),
    )
    return int(cur.lastrowid)


def _insert_alias(conn: sqlite3.Connection, *, person_id: int, alias_name: str, source_id: int, notes: str) -> bool:
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO person_aliases (person_id, alias_name, source_id, notes)
        VALUES (?, ?, ?, ?)
        """,
        (person_id, alias_name, source_id, notes),
    )
    return cur.rowcount == 1


def _insert_relationship(
    conn: sqlite3.Connection,
    *,
    low_id: int,
    high_id: int,
    relationship_type_code: str,
    strength: int,
    source_id: int,
    notes: str,
) -> bool:
    # UNIQUE constraint is (person_low_id, person_high_id, relationship_type_code, start_date)
    # start_date is NULL here, matching the Perry co-mention pattern.
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO relationships (
            person_low_id, person_high_id, relationship_type_code,
            strength, source_id, notes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (low_id, high_id, relationship_type_code, strength, source_id, notes),
    )
    return cur.rowcount == 1


def _write_locations_review(
    path: Path,
    location_letters: Dict[str, Set[str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(
        (
            (name, len(letters), ";".join(sorted(letters)))
            for name, letters in location_letters.items()
        ),
        key=lambda x: (-x[1], x[0].lower()),
    )
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "entity_name",
                "mention_letters_count",
                "letter_numbers",
                "suggested_place_type_code",  # to be filled in manually
                "parent_place_name",
                "parent_place_type_code",
                "region_sc_code",
                "modern_state",
                "action",                      # keep / drop / merge
                "notes",
            ]
        )
        for name, count, letters in rows:
            w.writerow([name, count, letters, "", "", "", "", "", "", ""])


def load(
    *,
    db_path: Path,
    csv_path: Path,
    locations_review_csv: Path,
    min_co_mentions: int,
    dry_run: bool,
) -> LoadStats:
    rows = _read_csv(csv_path)

    person_rows = [r for r in rows if r.entity_type == "PERSON"]
    location_rows = [r for r in rows if r.entity_type == "LOCATION"]

    # Aggregate locations for review CSV.
    location_letters: Dict[str, Set[str]] = defaultdict(set)
    for r in location_rows:
        location_letters[r.entity_name].add(r.letter_number)

    # Deduplicate alias inserts per (canonical_key, raw alias_name).
    person_raw_by_key: Dict[str, Set[str]] = defaultdict(set)
    for r in person_rows:
        person_raw_by_key[canonical_key_from_name(r.entity_name)].add(r.entity_name)

    # Per-letter participant sets, in canonical_key form.
    per_letter_keys: Dict[str, Set[str]] = defaultdict(set)
    for r in person_rows:
        if not r.letter_number:
            continue
        key = canonical_key_from_name(r.entity_name)
        if key and key != "unknown":
            per_letter_keys[r.letter_number].add(key)

    stats = LoadStats()

    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")

        # Provenance source rows.
        corpus_source_id = _get_or_create_source(
            conn,
            source_type_code="letter",
            title="James L. Petigru letters (corpus)",
            creator="Petigru NER pipeline",
            notes=(
                "Auto-generated from Petigru/letters via spaCy en_core_web_sm. "
                "Used to tag person_aliases derived from NER; not a claim of direct relationship."
            ),
        )
        comention_source_id = _get_or_create_source(
            conn,
            source_type_code="letter",
            title="James L. Petigru letters (co-mentions aggregated)",
            creator="Petigru NER pipeline",
            notes=(
                "Auto-generated co-mention edges: two PERSON entities appear in the same Petigru letter. "
                "Not a claim of direct relationship."
            ),
        )

        _ensure_lookup_relationship_type(conn, "co_mentioned", "Co-mentioned in correspondence")

        index = _build_person_index(conn)
        key_to_id: Dict[str, int] = dict(index.key_to_id)

        # Pass 1: resolve / insert people, insert aliases.
        for key, raw_names in person_raw_by_key.items():
            if not key or key == "unknown":
                continue
            pid = key_to_id.get(key)
            if pid is None:
                # Pick a representative display name: prefer longest with title-case look.
                display = sorted(raw_names, key=lambda x: (len(x), x))[-1]
                if dry_run:
                    pid = -len(key_to_id) - 1  # synthetic id for dry-run pairing
                else:
                    pid = _insert_person(
                        conn,
                        name=display,
                        note="From Petigru NER (auto-extracted; review recommended).",
                    )
                stats.people_inserted += 1
                key_to_id[key] = pid

            for raw in sorted(raw_names):
                if dry_run:
                    # Approximate: assume new alias only if it does not already match by raw text in DB.
                    exists = conn.execute(
                        "SELECT 1 FROM person_aliases WHERE person_id = ? AND alias_name = ?",
                        (pid if pid > 0 else 0, raw),
                    ).fetchone()
                    if exists:
                        stats.aliases_skipped_existing += 1
                    else:
                        stats.aliases_inserted += 1
                    continue

                inserted = _insert_alias(
                    conn,
                    person_id=pid,
                    alias_name=raw,
                    source_id=corpus_source_id,
                    notes="Petigru NER auto-extracted alias.",
                )
                if inserted:
                    stats.aliases_inserted += 1
                else:
                    stats.aliases_skipped_existing += 1

        # Pass 2: co-mention pairs.
        pair_counts: Counter[Tuple[int, int]] = Counter()
        for _letter, keys in per_letter_keys.items():
            ids = sorted({key_to_id[k] for k in keys if k in key_to_id and key_to_id[k] > 0})
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pair_counts[(ids[i], ids[j])] += 1

        stats.co_mention_pairs_considered = len(pair_counts)

        for (low_id, high_id), cnt in pair_counts.items():
            if cnt < min_co_mentions:
                continue
            stats.co_mention_pairs_kept += 1

            strength = _strength_from_count(cnt)
            notes = (
                f"Co-mentioned in Petigru letters (aggregated). "
                f"co_mention_letters_count={cnt}; min_count={min_co_mentions}; "
                f"inputs=Petigru/letters NER PERSON entities."
            )
            if dry_run:
                stats.relationships_inserted += 1
                continue

            inserted = _insert_relationship(
                conn,
                low_id=low_id,
                high_id=high_id,
                relationship_type_code="co_mentioned",
                strength=strength,
                source_id=comention_source_id,
                notes=notes,
            )
            if inserted:
                stats.relationships_inserted += 1
            else:
                stats.relationships_skipped_existing += 1

        # Locations review CSV (always written, regardless of dry-run).
        _write_locations_review(locations_review_csv, location_letters)
        stats.location_unique = len(location_letters)

        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.commit()

    finally:
        conn.close()

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Load Petigru NER entities into unionism.db (Option A: corpus source tagging).")
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument(
        "--csv",
        default="/Users/crboatwright/Petigru/Petigru_NER_entities.csv",
        help="Path to Petigru_NER_entities.csv produced by ner_letters_folder.py",
    )
    ap.add_argument(
        "--locations-review-csv",
        default="data/staging/petigru_ner_locations_review.csv",
        help="Where to write the locations-for-review CSV (created/overwritten).",
    )
    ap.add_argument(
        "--min-co-mentions",
        type=int,
        default=2,
        help="Minimum co-mention count (per pair across letters) to insert a relationship edge.",
    )
    ap.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    db_path = (repo_root / args.db).resolve()
    csv_path = Path(args.csv).expanduser().resolve()
    locations_csv = (repo_root / args.locations_review_csv).resolve()

    stats = load(
        db_path=db_path,
        csv_path=csv_path,
        locations_review_csv=locations_csv,
        min_co_mentions=int(args.min_co_mentions),
        dry_run=bool(args.dry_run),
    )

    print("Loaded Petigru NER entities")
    print(f"  DB: {db_path}")
    print(f"  CSV: {csv_path}")
    print(f"  Locations review CSV: {locations_csv}")
    print("People")
    print(f"  Inserted new people:        {stats.people_inserted}{' (dry-run)' if args.dry_run else ''}")
    print(f"  Aliases inserted:           {stats.aliases_inserted}{' (dry-run)' if args.dry_run else ''}")
    print(f"  Aliases already present:    {stats.aliases_skipped_existing}")
    print("Co-mentions")
    print(f"  Unique pairs considered:    {stats.co_mention_pairs_considered}")
    print(f"  Pairs kept (>= min):        {stats.co_mention_pairs_kept}")
    print(f"  Relationships inserted:     {stats.relationships_inserted}{' (dry-run)' if args.dry_run else ''}")
    print(f"  Relationships pre-existing: {stats.relationships_skipped_existing}")
    print("Locations")
    print(f"  Unique location strings:    {stats.location_unique}")


if __name__ == "__main__":
    main()
