"""Build a standalone HTML chart summarising the SCC student register against unionism.db.

Numbers (all computed from the database and the entry sheet):
  register students  = distinct names in scc_date_entry_sheet_tcl.csv
  matched            = people with SCC dates who also have data in the DB beyond the register
                       (positions, relationships, correspondence, other organizations or other sources)
  unionists / nullifiers = people with at least one position whose label contains
                       'unionist' / 'nullifier' (position_label_code)

Usage:  .venv/bin/python scripts/build_scc_register_chart.py
Output: data/scc_register_summary.html  (open in any browser; no external dependencies)
"""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "unionism.db"
SHEET = ROOT / "data" / "staging" / "scc_ocr" / "scc_date_entry_sheet_tcl.csv"
OUT = ROOT / "data" / "scc_register_summary.html"
REGISTER_SOURCE_ID = 22

db = sqlite3.connect(DB)

with open(SHEET, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
register_total = len({r["name_as_loaded"] for r in rows})
years = [int(r["start_year"]) for r in rows] + [int(r["end_year"]) for r in rows if r["end_year"]]
year_min, year_max = min(years), max(years)

scc = {r[0] for r in db.execute(
    "SELECT person_id FROM person_organization WHERE organization_id = 2 AND date_start IS NOT NULL")}


def has_other_data(pid):
    checks = [
        ("SELECT COUNT(*) FROM positions WHERE person_id = ?", (pid,)),
        ("SELECT COUNT(*) FROM relationships WHERE person_high_id = ? OR person_low_id = ?", (pid, pid)),
        ("SELECT COUNT(*) FROM correspondence WHERE sender_id = ? OR recipient_id = ?", (pid, pid)),
        ("SELECT COUNT(*) FROM person_organization WHERE person_id = ? AND organization_id <> 2", (pid,)),
        ("SELECT COUNT(*) FROM person_sources WHERE person_id = ? AND source_id <> ?", (pid, REGISTER_SOURCE_ID)),
    ]
    return any(db.execute(sql, args).fetchone()[0] > 0 for sql, args in checks)


matched = {p for p in scc if has_other_data(p)}
labels = db.execute("SELECT person_id, position_label_code FROM positions").fetchall()
unionists = {p for p, l in labels if "unionist" in l}
nullifiers = {p for p, l in labels if "nullifier" in l}

m_uni = matched & unionists
m_nul = matched & nullifiers
m_both = m_uni & m_nul
m_other = len(matched) - len(m_uni | m_nul)

n = dict(
    register=register_total,
    matched=len(matched),
    uni=len(m_uni),
    nul=len(m_nul),
    both=len(m_both),
    other=m_other,
    uni_all=len(unionists),
    nul_all=len(nullifiers),
)


def bar_rows(items, x0, width, scale_max, y0, row_h=46, bar_h=26):
    out = []
    for i, (label, value, color) in enumerate(items):
        y = y0 + i * row_h
        w = max(2, width * value / scale_max)
        out.append(f'<text x="{x0 - 12}" y="{y + 18}" text-anchor="end" class="lbl">{label}</text>')
        out.append(f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{color}"/>')
        out.append(f'<text x="{x0 + w + 8}" y="{y + 18}" class="val">{value:,}</text>')
    return "\n".join(out)


panel1 = bar_rows(
    [("Students in the register", n["register"], "#7a8ca5"),
     ("Matched to the unionism DB", n["matched"], "#2f6f8f")],
    x0=250, width=520, scale_max=n["register"], y0=20)
panel2 = bar_rows(
    [("Matched people", n["matched"], "#2f6f8f"),
     ("Known unionists", n["uni"], "#3a8f5c"),
     ("Known nullifiers", n["nul"], "#b5483a"),
     ("Both labels", n["both"], "#8a6bb0"),
     ("Neither (other or no stance)", n["other"], "#b8b8b8")],
    x0=250, width=520, scale_max=n["matched"], y0=20)

pct_uni = 100 * n["uni"] / n["uni_all"] if n["uni_all"] else 0
pct_nul = 100 * n["nul"] / n["nul_all"] if n["nul_all"] else 0

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>SCC register vs. unionism DB</title>
<style>
 body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 32px auto; max-width: 900px; color: #222; }}
 h1 {{ font-size: 22px; margin-bottom: 4px; }}
 h2 {{ font-size: 15px; margin: 28px 0 0; color: #444; }}
 .sub {{ color: #666; font-size: 13px; margin-bottom: 8px; }}
 .lbl {{ font-size: 14px; fill: #333; }}
 .val {{ font-size: 14px; font-weight: 600; fill: #222; }}
 .note {{ font-size: 12.5px; color: #555; line-height: 1.5; margin-top: 22px; }}
</style></head><body>
<h1>South Carolina College student register vs. the unionism database</h1>
<div class="sub">Register years {year_min}&ndash;{year_max}. Counts are people, not name entries.</div>

<h2>Register students and matches</h2>
<svg viewBox="0 0 900 110" width="100%">{panel1}</svg>

<h2>Of the {n['matched']} matched people</h2>
<svg viewBox="0 0 900 250" width="100%">{panel2}</svg>

<p class="note">
 Across the whole database there are {n['uni_all']} people with a unionist position and {n['nul_all']} with a nullifier position.
 Of those, {n['uni']} unionists ({pct_uni:.0f}%) and {n['nul']} nullifiers ({pct_nul:.0f}%) appear in the register.<br>
 <b>Matched</b> = a person with register dates who also has other data in the database (a position, relationship,
 correspondence, another organization or another source). <b>Unionist / nullifier</b> = at least one position whose
 label contains &ldquo;unionist&rdquo; or &ldquo;nullifier&rdquo; (all label variants, any issue).<br>
 Register names were read from page images and have not been verified; spelling variants were merged by rule, so
 the register total is approximate.
</p>
</body></html>
"""
OUT.write_text(html, encoding="utf-8")
print("wrote", OUT)
print(n)
