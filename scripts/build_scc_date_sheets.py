#!/usr/bin/env python3
"""Build SCC date-entry sheets (start/end year per student only).

Writes two CSVs into data/staging/scc_ocr/:

1. scc_page_header_map.csv  - one row per scanned page (1..72).
   Fill `page_year_start` / `page_year_end` ONLY when that range should apply to
   every name on the page (e.g. a single class-list page). Leave blank on
   multi-column pages where each student has their own dates; put any page
   date span in `notes` instead.

2. scc_date_entry_sheet.csv - one row per (student, page) taken from the
   existing pre-vetted CSVs, with the matching people.person_id from unionism.db.
   Fill start_year / end_year ONLY for pages that carry their own date columns
   (e.g. "time of becoming freshman" ... "bachelor of arts"). Leave blank on
   pages with a page-level year range; the loader will use that instead.

Per-person result (done later by the loader): start = earliest year seen,
end = latest year seen across all of that person's rows. Class level is
ignored; only the years at SCC matter.

The names are AI-read and UNVERIFIED. `verified_name` is for you to correct
or confirm against the page image.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "unionism.db"
OUT_DIR = ROOT / "data" / "staging" / "scc_ocr"
PAGES_DIR = OUT_DIR / "pages"
BATCHES = sorted(OUT_DIR.glob("scc_pre_vetted_batch*.csv"))

PAGE_RE = re.compile(r"page-(\d+)\.png$")


def main() -> None:
    # Page header map: one row per page image present on disk.
    page_nums = sorted(
        int(m.group(1)) for p in PAGES_DIR.glob("page-*.png") if (m := PAGE_RE.search(p.name))
    )
    header_path = OUT_DIR / "scc_page_header_map.csv"
    with header_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["png_page", "tcl_record", "layout", "page_year_start", "page_year_end", "notes"])
        for n in page_nums:
            # Digital record id = PNG number - 1 (id 0 is the front cover).
            tcl = n - 1
            w.writerow([n, tcl, "", "", "", ""])

    # Student sheet from the existing pre-vetted batches.
    conn = sqlite3.connect(DB)
    person_by_name = {
        row[0].lower(): row[1]
        for row in conn.execute("SELECT full_name, person_id FROM people ORDER BY person_id DESC")
    }
    conn.close()

    rows = []
    for batch in BATCHES:
        with batch.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                name = (r.get("reviewed_full_name") or "").strip()
                if not name:
                    continue
                rows.append(
                    {
                        "png_page": int(r["page_number"]),
                        "name_as_loaded": name,
                        "person_id": person_by_name.get(name.lower(), ""),
                        "start_year_loaded": (r.get("reviewed_start_year") or "").strip(),
                    }
                )
    rows.sort(key=lambda r: (r["png_page"], r["name_as_loaded"].lower()))

    sheet_path = OUT_DIR / "scc_date_entry_sheet.csv"
    with sheet_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "png_page",
                "name_as_loaded",
                "person_id",
                "verified_name",
                "start_year",
                "end_year",
                "notes",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r["png_page"],
                    r["name_as_loaded"],
                    r["person_id"],
                    "",
                    r["start_year_loaded"],
                    "",
                    "",
                ]
            )

    print(f"Wrote {header_path} ({len(page_nums)} pages)")
    print(f"Wrote {sheet_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
