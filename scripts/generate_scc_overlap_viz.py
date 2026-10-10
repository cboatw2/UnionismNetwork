#!/usr/bin/env python3
"""Generate a South Carolina College overlap/network visualization from unionism.db.

Outputs:
- app/static/visualizations/scc_overlap_network.html
- app/static/visualizations/scc_attendees.csv
- app/static/visualizations/scc_overlap_edges.csv
- app/static/visualizations/scc_relationship_edges.csv
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "unionism.db"
OUT_DIR = ROOT / "app" / "static" / "visualizations"


YEAR_RE = re.compile(r"(\d{4})")


@dataclass
class Attendee:
    person_id: int
    full_name: str
    role: Optional[str]
    date_start: Optional[str]
    date_end: Optional[str]

    @property
    def start_year(self) -> Optional[int]:
        return extract_year(self.date_start)

    @property
    def end_year(self) -> Optional[int]:
        return extract_year(self.date_end)


def extract_year(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    m = YEAR_RE.search(value)
    if not m:
        return None
    return int(m.group(1))


def overlap_range(a_start: Optional[int], a_end: Optional[int], b_start: Optional[int], b_end: Optional[int]) -> Optional[tuple[int, int]]:
    if a_start is None or a_end is None or b_start is None or b_end is None:
        return None
    left = max(a_start, b_start)
    right = min(a_end, b_end)
    if left <= right:
        return (left, right)
    return None


def fetch_attendees(conn: sqlite3.Connection) -> list[Attendee]:
    rows = conn.execute(
        """
        SELECT
            p.person_id,
            p.full_name,
            po.role,
            po.date_start,
            po.date_end
        FROM person_organization po
        JOIN organizations o ON o.organization_id = po.organization_id
        JOIN people p ON p.person_id = po.person_id
        WHERE o.name = 'South Carolina College'
        ORDER BY COALESCE(po.date_start, '9999'), p.full_name
        """
    ).fetchall()
    return [Attendee(*row) for row in rows]


def fetch_relationship_edges(conn: sqlite3.Connection, attendee_ids: set[int]) -> list[dict]:
    if not attendee_ids:
        return []
    placeholders = ",".join("?" for _ in attendee_ids)
    rows = conn.execute(
        f"""
        SELECT
            person_low_id,
            person_high_id,
            relationship_type_code,
            start_date,
            end_date
        FROM relationships
        WHERE person_low_id IN ({placeholders})
          AND person_high_id IN ({placeholders})
        ORDER BY relationship_type_code, person_low_id, person_high_id
        """,
        tuple(attendee_ids) + tuple(attendee_ids),
    ).fetchall()

    out = []
    for low_id, high_id, rel_type, start_date, end_date in rows:
        out.append(
            {
                "from": int(low_id),
                "to": int(high_id),
                "relationship_type": rel_type,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
    return out


def build_overlap_edges(attendees: list[Attendee]) -> list[dict]:
    edges = []
    for i in range(len(attendees)):
        a = attendees[i]
        for j in range(i + 1, len(attendees)):
            b = attendees[j]
            ov = overlap_range(a.start_year, a.end_year, b.start_year, b.end_year)
            if ov is None:
                continue
            edges.append(
                {
                    "from": a.person_id,
                    "to": b.person_id,
                    "overlap_start": ov[0],
                    "overlap_end": ov[1],
                    "overlap_years": ov[1] - ov[0] + 1,
                }
            )
    return edges


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_html(attendees: list[Attendee], overlap_edges: list[dict], relationship_edges: list[dict]) -> str:
    attendee_payload = []
    for a in attendees:
        year_text = f"{a.start_year or '?'}-{a.end_year or '?'}"
        attendee_payload.append(
            {
                "id": a.person_id,
                "label": a.full_name,
                "title": f"{a.full_name}<br>Role: {a.role or 'Unknown'}<br>Years: {year_text}",
                "start_year": a.start_year,
                "end_year": a.end_year,
                "role": a.role,
                "group": "known" if (a.start_year is not None and a.end_year is not None) else "partial",
            }
        )

    overlap_payload = []
    for e in overlap_edges:
        overlap_payload.append(
            {
                "from": e["from"],
                "to": e["to"],
                "label": f"SCC overlap {e['overlap_start']}-{e['overlap_end']}",
                "title": f"Shared years at SCC: {e['overlap_start']}-{e['overlap_end']} ({e['overlap_years']} years)",
                "color": {"color": "#1f78b4"},
                "dashes": True,
                "width": 1 + min(e["overlap_years"], 6),
                "kind": "overlap",
            }
        )

    rel_payload = []
    for e in relationship_edges:
        start_y = extract_year(e["start_date"])
        end_y = extract_year(e["end_date"])
        rel_payload.append(
            {
                "from": e["from"],
                "to": e["to"],
                "label": e["relationship_type"],
                "title": f"Network tie: {e['relationship_type']}<br>Date: {e['start_date'] or '?'} to {e['end_date'] or '?'}",
                "color": {"color": "#d95f02"},
                "dashes": False,
                "width": 2,
                "kind": "relationship",
                "start_year": start_y,
                "end_year": end_y,
            }
        )

    html_template = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>SCC Attendance Overlap Network</title>
  <script src=\"https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js\"></script>
  <style>
    :root {{
      --bg: #f4f1e8;
      --panel: #fffaf0;
      --ink: #1f1f1f;
      --muted: #4a4a4a;
      --blue: #1f78b4;
      --orange: #d95f02;
      --line: #c8bfae;
    }}
    body {{
      margin: 0;
      font-family: Georgia, 'Times New Roman', serif;
      color: var(--ink);
      background: radial-gradient(circle at 15% 15%, #fffbe9 0%, var(--bg) 55%);
    }}
    .wrap {{
      max-width: 1200px;
      margin: 22px auto;
      padding: 0 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
      padding: 14px;
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-size: 1.55rem;
      letter-spacing: 0.01em;
    }}
    .sub {{
      color: var(--muted);
      margin-bottom: 12px;
      line-height: 1.45;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 10px 0 10px;
      font-size: 0.95rem;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }}
    #network {{
      width: 100%;
      height: 68vh;
      min-height: 480px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: center;
      margin: 12px 0;
      font-size: 0.95rem;
    }}
    .meta {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <h1>South Carolina College: Attendance Years + Network Overlap</h1>
      <div class=\"sub\">Dashed blue edges show overlapping years at South Carolina College. Solid orange edges show existing relationship ties in Unionism Network data.</div>

      <div class=\"legend\">
        <span class=\"chip\"><span class=\"dot\" style=\"background:#2e8b57\"></span>Attendee (start/end years known)</span>
        <span class=\"chip\"><span class=\"dot\" style=\"background:#8f8f8f\"></span>Attendee (partial years)</span>
        <span class=\"chip\"><span style=\"width:22px; border-top:2px dashed var(--blue); display:inline-block\"></span>Year overlap</span>
        <span class=\"chip\"><span style=\"width:22px; border-top:2px solid var(--orange); display:inline-block\"></span>Network tie</span>
      </div>

      <div class=\"controls\">
        <label><input type=\"checkbox\" id=\"showOverlap\" checked /> Show year-overlap edges</label>
        <label><input type=\"checkbox\" id=\"showRel\" checked /> Show relationship edges</label>
      </div>

      <div id=\"network\"></div>
      <div class=\"meta\" id=\"meta\"></div>
    </div>
  </div>

  <script>
    const attendeeNodes = __ATTENDEE_JSON__;
    const overlapEdges = __OVERLAP_JSON__;
    const relationshipEdges = __REL_JSON__;

    const nodes = new vis.DataSet(attendeeNodes.map(n => ({
      ...n,
      shape: 'dot',
      size: 18,
      font: {{ face: 'Georgia', size: 15 }},
      color: n.group === 'known'
        ? {{ background: '#2e8b57', border: '#1f5f3e', highlight: {{ background: '#3ca86a', border: '#1f5f3e' }} }}
        : {{ background: '#8f8f8f', border: '#5f5f5f', highlight: {{ background: '#a3a3a3', border: '#5f5f5f' }} }}
    })));

    const allEdges = [...overlapEdges, ...relationshipEdges];
    const edges = new vis.DataSet(allEdges);

    const network = new vis.Network(
      document.getElementById('network'),
      {{ nodes, edges }},
      {{
        interaction: {{ hover: true, tooltipDelay: 90 }},
        physics: {{
          stabilization: true,
          barnesHut: {{ gravitationalConstant: -2400, springLength: 175, springConstant: 0.03 }}
        }},
        edges: {{
          smooth: {{ type: 'dynamic' }},
          font: {{ align: 'middle', size: 11, face: 'Georgia' }}
        }},
        layout: {{ improvedLayout: true }}
      }}
    );

    function renderMeta() {{
      const n = attendeeNodes.length;
      const o = overlapEdges.length;
      const r = relationshipEdges.length;
      document.getElementById('meta').textContent = `Attendees: ${{n}} | Overlap edges: ${{o}} | Relationship edges: ${{r}}`;
    }}

    function applyFilters() {{
      const showOverlap = document.getElementById('showOverlap').checked;
      const showRel = document.getElementById('showRel').checked;
      const filtered = allEdges.filter(e =>
        (showOverlap && e.kind === 'overlap') ||
        (showRel && e.kind === 'relationship')
      );
      edges.clear();
      edges.add(filtered);
    }}

    document.getElementById('showOverlap').addEventListener('change', applyFilters);
    document.getElementById('showRel').addEventListener('change', applyFilters);

    applyFilters();
    renderMeta();
  </script>
</body>
</html>
"""
    html_template = html_template.replace("{{", "{").replace("}}", "}")

    return (
      html_template.replace("__ATTENDEE_JSON__", json.dumps(attendee_payload, ensure_ascii=False))
        .replace("__OVERLAP_JSON__", json.dumps(overlap_payload, ensure_ascii=False))
        .replace("__REL_JSON__", json.dumps(rel_payload, ensure_ascii=False))
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    attendees = fetch_attendees(conn)
    attendee_ids = {a.person_id for a in attendees}
    overlap_edges = build_overlap_edges(attendees)
    relationship_edges = fetch_relationship_edges(conn, attendee_ids)
    conn.close()

    attendee_rows = [
        {
            "person_id": a.person_id,
            "full_name": a.full_name,
            "role": a.role,
            "date_start": a.date_start,
            "date_end": a.date_end,
            "start_year": a.start_year,
            "end_year": a.end_year,
        }
        for a in attendees
    ]

    write_csv(
        OUT_DIR / "scc_attendees.csv",
        ["person_id", "full_name", "role", "date_start", "date_end", "start_year", "end_year"],
        attendee_rows,
    )
    write_csv(
        OUT_DIR / "scc_overlap_edges.csv",
        ["from", "to", "overlap_start", "overlap_end", "overlap_years"],
        overlap_edges,
    )
    write_csv(
        OUT_DIR / "scc_relationship_edges.csv",
        ["from", "to", "relationship_type", "start_date", "end_date"],
        relationship_edges,
    )

    html = build_html(attendees, overlap_edges, relationship_edges)
    (OUT_DIR / "scc_overlap_network.html").write_text(html, encoding="utf-8")

    summary = {
        "attendees": len(attendees),
        "overlap_edges": len(overlap_edges),
        "relationship_edges": len(relationship_edges),
        "output_html": str((OUT_DIR / "scc_overlap_network.html").relative_to(ROOT)),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
