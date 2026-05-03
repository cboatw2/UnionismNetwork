from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


REVIEW_COLUMNS = [
    "raw_person_id",
    "raw_name",
    "normalized_name",
    "canonical_key",
    "suggested_canonical_name",
    "mention_letters_count",
    "sender_letters_count",
    "recipient_letters_count",
    "action",  # keep, merge, drop, review
    "canonical_name_override",
    "notes",
]

UNIONISM_PEOPLE_COLUMNS = [
    "canonical_key",
    "full_name",
    "display_name",
    "birth_year",
    "death_year",
    "birth_place_id",
    "death_place_id",
    "race_code",
    "gender",
    "class_code",
    "occupation",
    "home_region_sc_code",
    "enslaved_status",
    "source_density_code",
    "representation_depth_code",
    "erasure_flag",
    "erasure_reason_code",
    "notes",
]

ALIASES_STAGING_COLUMNS = [
    "canonical_key",
    "alias_name",
    "source_id",
    "notes",
]

ALLOWED_ACTIONS = {"keep", "merge", "drop", "review"}


def _clean(s: str | None) -> str:
    return (s or "").strip()


def _pick_longest(values: list[str]) -> str:
    cleaned = [v.strip() for v in values if v and v.strip()]
    if not cleaned:
        return ""
    cleaned.sort(key=lambda x: (len(x), x.lower()), reverse=True)
    return cleaned[0]


@dataclass(frozen=True)
class ReviewRow:
    raw_person_id: str
    raw_name: str
    canonical_key: str
    suggested_canonical_name: str
    action: str
    canonical_name_override: str
    notes: str


def read_review_rows(path: Path) -> list[ReviewRow]:
    if not path.exists():
        raise SystemExit(f"Review CSV not found: {path}")
    try:
        size = path.stat().st_size
    except OSError:
        size = None

    if size == 0:
        raise SystemExit(
            "Review CSV is empty (0 bytes). If you edited it in VS Code, make sure you saved the file to disk, "
            "then re-run this script."
        )

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(
                "Could not read a CSV header row (fieldnames is empty). "
                "Confirm the file is a valid comma-separated CSV and is saved to disk."
            )
        missing = [c for c in REVIEW_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(
                f"Review CSV is missing required columns: {missing}. "
                f"Found: {reader.fieldnames}"
            )

        rows: list[ReviewRow] = []
        for i, r in enumerate(reader, start=2):
            canonical_key = _clean(r.get("canonical_key"))
            if not canonical_key:
                raise SystemExit(f"Empty canonical_key at {path}:{i}")

            action = _clean(r.get("action")).lower() or "review"
            if action not in ALLOWED_ACTIONS:
                raise SystemExit(
                    f"Invalid action '{action}' at {path}:{i}. "
                    f"Allowed: {sorted(ALLOWED_ACTIONS)}"
                )

            rows.append(
                ReviewRow(
                    raw_person_id=_clean(r.get("raw_person_id")),
                    raw_name=_clean(r.get("raw_name")),
                    canonical_key=canonical_key,
                    suggested_canonical_name=_clean(r.get("suggested_canonical_name")),
                    action=action,
                    canonical_name_override=_clean(r.get("canonical_name_override")),
                    notes=_clean(r.get("notes")),
                )
            )
    return rows


def build_people_and_aliases(rows: list[ReviewRow]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    included = [r for r in rows if r.action in ("keep", "merge")]

    grouped: dict[str, list[ReviewRow]] = defaultdict(list)
    for r in included:
        grouped[r.canonical_key].append(r)

    people_rows: list[dict[str, str]] = []
    alias_rows: list[dict[str, str]] = []
    seen_alias: set[tuple[str, str]] = set()

    for canonical_key, group in sorted(grouped.items(), key=lambda kv: kv[0]):
        overrides = sorted({r.canonical_name_override for r in group if r.canonical_name_override})
        if len(overrides) > 1:
            # Keep deterministic behavior; surface the conflict in notes.
            chosen_name = overrides[0]
            name_note = f"Conflicting canonical_name_override values={overrides}; chose {chosen_name!r}."
        elif len(overrides) == 1:
            chosen_name = overrides[0]
            name_note = ""
        else:
            chosen_name = _pick_longest([r.suggested_canonical_name for r in group]) or _pick_longest(
                [r.raw_name for r in group]
            )
            name_note = ""

        raw_ids = sorted({r.raw_person_id for r in group if r.raw_person_id})
        evidence_note = f"From people_review; raw_person_ids={','.join(raw_ids) if raw_ids else 'unknown'}"

        people_note_parts = [evidence_note]
        if name_note:
            people_note_parts.append(name_note)

        people_rows.append(
            {
                "canonical_key": canonical_key,
                "full_name": chosen_name,
                "display_name": chosen_name,
                "birth_year": "",
                "death_year": "",
                "birth_place_id": "",
                "death_place_id": "",
                "race_code": "",
                "gender": "",
                "class_code": "",
                "occupation": "",
                "home_region_sc_code": "",
                "enslaved_status": "",
                "source_density_code": "",
                "representation_depth_code": "",
                "erasure_flag": "0",
                "erasure_reason_code": "",
                "notes": " ".join(people_note_parts),
            }
        )

        for r in group:
            alias = r.raw_name
            if not alias:
                continue
            dedupe_key = (canonical_key, alias.lower())
            if dedupe_key in seen_alias:
                continue
            seen_alias.add(dedupe_key)

            alias_note = f"From people_review raw_person_id={r.raw_person_id or 'unknown'}"
            if r.notes:
                alias_note = f"{alias_note}; {r.notes}"

            alias_rows.append(
                {
                    "canonical_key": canonical_key,
                    "alias_name": alias,
                    "source_id": "",
                    "notes": alias_note,
                }
            )

    return people_rows, alias_rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply edits in people_review_edited.csv and regenerate staging CSVs. "
            "Merges are performed by grouping rows by canonical_key; rows with action=drop are excluded."
        )
    )
    parser.add_argument(
        "--review-csv",
        default="data/staging/people_review_edited.csv",
        help="Path to edited people_review CSV",
    )
    parser.add_argument(
        "--out-dir",
        default="data/staging",
        help="Output directory for regenerated staging CSVs",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite unionism_people_staging.csv and unionism_aliases_staging.csv in out-dir",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    review_path = (repo_root / args.review_csv).resolve()
    out_dir = (repo_root / args.out_dir).resolve()

    rows = read_review_rows(review_path)
    people_rows, alias_rows = build_people_and_aliases(rows)

    if args.overwrite:
        people_out = out_dir / "unionism_people_staging.csv"
        alias_out = out_dir / "unionism_aliases_staging.csv"
    else:
        people_out = out_dir / "unionism_people_staging_from_review.csv"
        alias_out = out_dir / "unionism_aliases_staging_from_review.csv"

    write_csv(people_out, UNIONISM_PEOPLE_COLUMNS, people_rows)
    write_csv(alias_out, ALIASES_STAGING_COLUMNS, alias_rows)

    dropped = sum(1 for r in rows if r.action == "drop")
    print("Read:")
    print(f"  {review_path} ({len(rows)} rows; dropped={dropped})")
    print("Wrote:")
    print(f"  {people_out} ({len(people_rows)} people)")
    print(f"  {alias_out} ({len(alias_rows)} aliases)")


if __name__ == "__main__":
    main()
