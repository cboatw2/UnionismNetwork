"""Build a printable list of the people in the South Carolina College organization (unionism.db).

Usage:  .venv/bin/python scripts/build_scc_matches_list.py
Output: data/scc_matches_printable.html  (open in a browser and print, or save as PDF)
"""
import sqlite3
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "unionism.db"
OUT = ROOT / "data" / "scc_matches_printable.html"

db = sqlite3.connect(DB)

people = db.execute(
    """
    SELECT p.person_id, p.full_name, MIN(po.date_start), MAX(po.date_end)
    FROM person_organization po JOIN people p USING (person_id)
    WHERE po.organization_id = 2 AND po.date_start IS NOT NULL
    GROUP BY p.person_id
    """
).fetchall()

labels = db.execute("SELECT person_id, position_label_code FROM positions").fetchall()
unionists = {p for p, l in labels if "unionist" in l}
nullifiers = {p for p, l in labels if "nullifier" in l}


def display(name):
    return name.title() if name.isupper() else name


def surname_key(row):
    parts = display(row[1]).replace(",", " ").split()
    return (parts[-1].lower(), display(row[1]).lower())


body = []
for i, (pid, name, start, end) in enumerate(sorted(people, key=surname_key), 1):
    stance = [s for s, group in (("Unionist", unionists), ("Nullifier", nullifiers)) if pid in group]
    years = start if not end or end == start else f"{start}&ndash;{end}"
    body.append(
        f"<tr><td class='n'>{i}</td><td>{escape(display(name))}</td><td>{years}</td>"
        f"<td>{' / '.join(stance) or '&mdash;'}</td><td class='blank'></td></tr>"
    )

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>South Carolina College register matches</title>
<style>
 @page {{ margin: 0.7in; }}
 body {{ font-family: Georgia, 'Times New Roman', serif; color: #000; margin: 24px auto; max-width: 820px; }}
 h1 {{ font-size: 18px; margin: 0 0 2px; }}
 .sub {{ font-size: 12px; color: #444; margin-bottom: 14px; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
 th, td {{ text-align: left; padding: 4px 8px; border-bottom: 1px solid #bbb; vertical-align: top; }}
 th {{ border-bottom: 2px solid #000; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
 td.n {{ width: 28px; color: #555; text-align: right; }}
 td.blank {{ width: 30%; }}
 tr {{ page-break-inside: avoid; }}
 thead {{ display: table-header-group; }}
</style></head><body>
<h1>South Carolina College register: people matched to the unionism database</h1>
<div class="sub">{len(people)} people &middot; sorted by surname &middot; generated {date.today().isoformat()}.
 SCC years are from the student register (names read from page images, not independently verified).
 Stance = any unionist or nullifier position coded in the database.</div>
<table>
<thead><tr><th>#</th><th>Name</th><th>SCC years</th><th>Stance in DB</th><th>Notes</th></tr></thead>
<tbody>
{chr(10).join(body)}
</tbody>
</table>
</body></html>
"""
OUT.write_text(html, encoding="utf-8")
print("wrote", OUT, len(people), "people")
