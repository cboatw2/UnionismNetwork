from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


_slug_re = re.compile(r"[a-z0-9]+")


def _slugify(text: str) -> str:
    t = text.strip().lower()
    t = t.replace("&", " and ")
    parts = _slug_re.findall(t)
    return "_".join(parts)


@dataclass(frozen=True)
class ProposedIssue:
    code: str
    label: str


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _fetch_distinct_event_values(conn: sqlite3.Connection, source: str) -> List[str]:
    if source == "event_name":
        rows = conn.execute(
            "SELECT DISTINCT event_name AS v FROM events WHERE event_name IS NOT NULL AND trim(event_name) <> '' ORDER BY event_name"
        ).fetchall()
    elif source == "event_type_code":
        rows = conn.execute(
            "SELECT DISTINCT event_type_code AS v FROM events WHERE event_type_code IS NOT NULL AND trim(event_type_code) <> '' ORDER BY event_type_code"
        ).fetchall()
    else:
        raise SystemExit(f"Unknown source: {source!r}")

    return [str(r[0]) for r in rows]


def _propose_issues(values: Iterable[str], *, prefix: str) -> List[ProposedIssue]:
    proposed: List[ProposedIssue] = []
    for v in values:
        slug = _slugify(v)
        if not slug:
            continue
        code = slug
        if code[0].isdigit():
            code = f"{prefix}{code}"
        proposed.append(ProposedIssue(code=code, label=v.strip()))
    return proposed


def seed_from_events(*, db_path: Path, source: str, prefix: str, apply: bool) -> None:
    conn = _connect(db_path)
    try:
        values = _fetch_distinct_event_values(conn, source)
        proposed = _propose_issues(values, prefix=prefix)

        existing_by_code = {
            r["issue_category_code"]: r["label"]
            for r in conn.execute("SELECT issue_category_code, label FROM lkp_issue_category").fetchall()
        }
        existing_labels = {lbl for lbl in existing_by_code.values()}

        inserts: List[ProposedIssue] = []
        warnings: List[str] = []

        for p in proposed:
            if p.code in existing_by_code:
                if existing_by_code[p.code] != p.label:
                    warnings.append(
                        f"Code already exists with different label: {p.code!r} existing={existing_by_code[p.code]!r} proposed={p.label!r}"
                    )
                continue
            if p.label in existing_labels:
                warnings.append(
                    f"Label already exists under a different code; skipping: label={p.label!r} proposed_code={p.code!r}"
                )
                continue
            inserts.append(p)

        print("Seed issue categories from events")
        print(f"  DB: {db_path}")
        print(f"  Source: {source}")
        print(f"  Proposed: {len(proposed)}")
        print(f"  New inserts: {len(inserts)}")
        if warnings:
            print(f"  Warnings: {len(warnings)}")

        if inserts:
            print("\nNew issue categories:")
            for p in inserts:
                print(f"  {p.code} -> {p.label}")

        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"  - {w}")

        if not apply:
            print("\nDry-run only (no DB changes). Re-run with --apply to insert.")
            return

        conn.execute("BEGIN")
        for p in inserts:
            conn.execute(
                "INSERT OR IGNORE INTO lkp_issue_category (issue_category_code, label) VALUES (?, ?)",
                (p.code, p.label),
            )
        conn.commit()
        print("\nApplied.")

    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Seed lkp_issue_category entries from values already present in events. "
            "Useful when your events list is becoming your working issue vocabulary."
        )
    )
    ap.add_argument("--db", default="unionism.db")
    ap.add_argument(
        "--from",
        dest="source",
        default="event_name",
        choices=["event_name", "event_type_code"],
        help="Which events column to seed from.",
    )
    ap.add_argument(
        "--prefix",
        default="event_",
        help="Prefix added if a generated code would start with a digit.",
    )
    ap.add_argument("--apply", action="store_true", help="Write inserts to DB (default is dry-run).")

    args = ap.parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    seed_from_events(
        db_path=(repo_root / args.db).resolve(),
        source=str(args.source),
        prefix=str(args.prefix),
        apply=bool(args.apply),
    )


if __name__ == "__main__":
    main()
