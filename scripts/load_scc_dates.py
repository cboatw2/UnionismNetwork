#!/usr/bin/env python3
"""Attach SCC attendance start/end years to South Carolina College students.

Model: every listing of a name on a register page is one observation with one
year (or, on eight-column pages, a start and end year typed by the user).
A person's date_start = earliest year observed, date_end = latest year observed.
Class level is ignored.

Year for each entry-sheet row:
  1. start_year / end_year typed in the entry sheet (end defaults to start), else
  2. the page's single year from the header map (page_year_start/page_year_end), else
  3. nothing -> row is reported as "needs year" and ignored.

Page key is tcl_page if the sheet has it, otherwise png_page - 1 (TCL record id,
the number shown in the digital-library page title).

Default is a dry run that writes a preview CSV and changes nothing.
Use --commit to write; the DB is backed up first.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "staging" / "scc_ocr"
SOURCE_ID = 22
SCC_ORG_NAME = "South Carolina College"
LINK = "https://digital.tcl.sc.edu/digital/collection/usc-sr/id/{}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=str(ROOT / "unionism.db"))
    p.add_argument("--header-map", default=str(STAGING / "scc_page_header_map_merged.csv"))
    p.add_argument("--entry-sheet", default=str(STAGING / "scc_date_entry_sheet.csv"))
    p.add_argument("--preview", default=str(STAGING / "scc_dates_preview.csv"))
    p.add_argument("--commit", action="store_true", help="write to the DB (default is dry run)")
    return p.parse_args()


def year(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        y = int(s)
    except ValueError:
        raise SystemExit(f"Bad year value: {s!r}")
    if not 1800 <= y <= 1900:
        raise SystemExit(f"Year out of range: {y}")
    return y


def main() -> None:
    args = parse_args()

    page_year = {}
    with open(args.header_map, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            page_year[int(r["tcl_record"])] = (year(r["page_year_start"]), year(r["page_year_end"]))

    with open(args.entry_sheet, encoding="utf-8", newline="") as f:
        sheet = list(csv.DictReader(f))

    conn = sqlite3.connect(args.db)
    org_id = conn.execute("SELECT organization_id FROM organizations WHERE name=?", (SCC_ORG_NAME,)).fetchone()[0]

    # person key -> observations
    obs = defaultdict(lambda: {"name": None, "person_id": None, "years": [], "pages": set(), "verified": False})
    needs_year, no_person = [], []

    for r in sheet:
        if (r.get("tcl_page") or "").strip():
            tcl = int(r["tcl_page"])
        elif (r.get("png_page") or "").strip():
            tcl = int(r["png_page"]) - 1
        else:
            continue
        verified = (r.get("verified_name") or "").strip()
        name = verified or (r.get("name_as_loaded") or "").strip()
        if not name:
            continue
        pid = (r.get("person_id") or "").strip()
        pid = int(pid) if pid else None
        if pid is None:
            row = conn.execute("SELECT person_id FROM people WHERE lower(full_name)=lower(?) LIMIT 1", (name,)).fetchone()
            pid = row[0] if row else None
        key = pid if pid is not None else name.lower()

        ys, ye = year(r.get("start_year")), year(r.get("end_year"))
        if ys is not None and ye is None:
            ye = ys
        if ys is None and ye is not None:
            ys = ye
        if ys is None:
            ys, ye = page_year.get(tcl, (None, None))
        if ys is None:
            needs_year.append((tcl, name))
            continue

        o = obs[key]
        o["name"] = o["name"] or name
        o["person_id"] = pid
        o["years"] += [ys, ye]
        o["pages"].add(tcl)
        o["verified"] = o["verified"] or bool(verified)

    preview, updates, inserts, creates = [], 0, 0, 0
    backup = None
    if args.commit:
        backup = Path(args.db).with_name(f"{Path(args.db).name}.bak_pre_scc_dates_{datetime.now():%Y%m%d_%H%M%S}")
        shutil.copy2(args.db, backup)

    conn.execute("BEGIN")
    for key, o in sorted(obs.items(), key=lambda kv: kv[1]["name"].lower()):
        ds, de = min(o["years"]), max(o["years"])
        pages = sorted(o["pages"])
        note = (
            "Student Registers, Vol. 01, 1806-1835, digital page id(s) "
            + ", ".join(str(p) for p in pages)
            + " ("
            + "; ".join(LINK.format(p) for p in pages)
            + "). Dates = earliest and latest year the name is listed; class level not recorded. "
            + ("Name verified by researcher." if o["verified"] else "Name AI-transcribed from page image (unverified).")
        )
        pid = o["person_id"]
        action = ""
        if pid is None:
            action = "create person + insert"
            creates += 1
            inserts += 1
            if args.commit:
                cur = conn.execute("INSERT INTO people (full_name, display_name, notes) VALUES (?,?,?)",
                                   (o["name"], o["name"], "SCC register name entered by researcher."))
                pid = cur.lastrowid
        if pid is not None:
            rows = conn.execute(
                "SELECT person_org_id, date_start, date_end FROM person_organization "
                "WHERE person_id=? AND organization_id=? AND role='Student' AND source_id=? ORDER BY person_org_id",
                (pid, org_id, SOURCE_ID),
            ).fetchall()
            if rows:
                prev = f"{rows[0][1]}-{rows[0][2]}" if rows[0][1] else ""
                action = "update" + (f" (was {prev})" if prev else "")
                updates += 1
                if args.commit:
                    conn.execute("UPDATE person_organization SET date_start=?, date_end=?, notes=? WHERE person_org_id=?",
                                 (str(ds), str(de), note, rows[0][0]))
                if len(rows) > 1:
                    action += f" [{len(rows)} existing rows; only first updated]"
            elif not action:
                action = "insert"
                inserts += 1
            if not rows and args.commit:
                conn.execute(
                    "INSERT INTO person_organization (person_id, organization_id, role, date_start, date_end, source_id, notes) "
                    "VALUES (?,?,'Student',?,?,?,?)",
                    (pid, org_id, str(ds), str(de), SOURCE_ID, note),
                )
        preview.append({"person_id": pid or "", "name": o["name"], "tcl_pages": " ".join(map(str, pages)),
                        "date_start": ds, "date_end": de, "name_verified": o["verified"], "action": action})

    if args.commit:
        conn.commit()
    else:
        conn.rollback()
    conn.close()

    with open(args.preview, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["person_id", "name", "tcl_pages", "date_start", "date_end", "name_verified", "action"])
        w.writeheader()
        w.writerows(preview)

    print(f"people with dates: {len(preview)}  (updates {updates}, inserts {inserts}, new people {creates})")
    print(f"name verified by you: {sum(1 for p in preview if p['name_verified'])}")
    print(f"rows needing a year (range or eight-column page, no year typed): {len(needs_year)}")
    for tcl, name in needs_year[:40]:
        print(f"   TCL {tcl}: {name}")
    if len(needs_year) > 40:
        print(f"   ... {len(needs_year) - 40} more")
    print(f"preview written: {args.preview}")
    print("committed:", args.commit, f"(backup {backup})" if backup else "")


if __name__ == "__main__":
    main()
