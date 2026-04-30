from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db

APP_TITLE = "Unionism Network"


def _year_from_date_expr(col: str) -> str:
    # Dates are stored as TEXT (ISO-ish). We treat the first 4 chars as year.
    # If the value is NULL, year is NULL.
    return f"CAST(substr({col}, 1, 4) AS INTEGER)"


def _interval_active_at_year(start_col: str, end_col: str, year_param: str = ":year") -> str:
    start_year = _year_from_date_expr(start_col)
    end_year = _year_from_date_expr(end_col)
    return (
        f"(({start_col} IS NULL) OR ({start_year} IS NOT NULL AND {start_year} <= {year_param})) "
        f"AND (({end_col} IS NULL) OR ({end_year} IS NOT NULL AND {end_year} >= {year_param}))"
    )


app = FastAPI(title=APP_TITLE)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(static_dir / "index.html"))


@app.get("/api/meta")
def meta() -> Dict[str, Any]:
    with db.get_conn() as conn:
        issues = db.fetch_all(
            conn,
            "SELECT issue_category_code AS code, label FROM lkp_issue_category ORDER BY label",
        )
        scales = db.fetch_all(
            conn,
            "SELECT scale_level_code AS code, label FROM lkp_scale_level ORDER BY scale_level_code",
        )
        people = db.fetch_all(
            conn,
            "SELECT person_id, full_name, display_name, home_region_sc_code FROM people ORDER BY COALESCE(display_name, full_name)",
        )

    return {
        "years": {"min": 1817, "max": 1865, "step": 1},
        "issues": issues,
        "scales": scales,
        "people": people,
    }


@app.get("/api/state")
def state(
    year: int = Query(..., ge=1500, le=2100),
    issue: str = Query("nullification"),
    scale: Optional[str] = Query(None),
) -> Dict[str, Any]:
    with db.get_conn() as conn:
        # People / nodes
        nodes_sql = """
        SELECT
            p.person_id,
            COALESCE(p.display_name, p.full_name) AS name,
            p.full_name,
            p.display_name,
            p.birth_place_id,
            p.home_region_sc_code,
            p.source_density_code,
            p.representation_depth_code,
            -- Selected stance claim for (person, issue) active at this year: pick the most recent start.
            (
                SELECT pos.position_label_code
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS position_label_code,
            (
                SELECT pos.stance_on_union
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_on_union,
            (
                SELECT pos.stance_on_states_rights
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_on_states_rights,
            (
                SELECT pos.stance_on_slavery
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_on_slavery,
            (
                SELECT pos.stance_on_secession
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_on_secession,
            (
                SELECT pos.confidence_score
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_confidence,
            (
                SELECT pos.source_id
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_source_id,
            (
                SELECT pos.justification_note
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_justification,
            -- Map position (place) for this year: prefer a residence active at this year; else birthplace.
                        COALESCE(
                                (
                                        SELECT r.place_id
                                        FROM person_place_residence r
                                        WHERE r.person_id = p.person_id
                                            AND """ + _interval_active_at_year("r.date_start", "r.date_end") + """
                                        ORDER BY """ + _year_from_date_expr("r.date_start") + """ DESC
                                        LIMIT 1
                                ),
                                p.birth_place_id
                        ) AS map_place_id
        FROM people p
        ORDER BY name;
        """

        cur = conn.execute(nodes_sql, {"year": year, "issue": issue})
        nodes = [dict(r) for r in cur.fetchall()]

        place_ids = {n.get("map_place_id") for n in nodes if n.get("map_place_id") is not None}

        if place_ids:
            placeholders = ",".join(["?"] * len(place_ids))
            places = db.fetch_all(
                conn,
                f"SELECT place_id, place_name, latitude, longitude, place_type_code, region_sc_code, modern_state FROM places WHERE place_id IN ({placeholders})",
                tuple(place_ids),
            )
        else:
            places = []

        places_by_id = {p["place_id"]: p for p in places}
        for n in nodes:
            place = places_by_id.get(n.get("map_place_id"))
            if place:
                n["map_place"] = place
            else:
                n["map_place"] = None

        # Relationships / edges
        edges_sql = """
        SELECT
            rel.relationship_id,
            rel.person_low_id AS source,
            rel.person_high_id AS target,
            rel.relationship_type_code,
            rel.strength AS baseline_strength,
            rel.alignment_status_code AS baseline_alignment_status,
            rel.source_id AS baseline_source_id,
            -- Most recent issue-specific characterization active at this year
            (
                SELECT rc.alignment_status_code
                FROM relationship_characterizations rc
                WHERE rc.relationship_id = rel.relationship_id
                  AND rc.issue_category_code = :issue
                  AND ( :scale IS NULL OR rc.scale_level_code = :scale )
                  AND """ + _interval_active_at_year("rc.date_start", "rc.date_end") + """
                ORDER BY """ + _year_from_date_expr("rc.date_start") + """ DESC
                LIMIT 1
            ) AS alignment_status_code,
            (
                SELECT rc.strength
                FROM relationship_characterizations rc
                WHERE rc.relationship_id = rel.relationship_id
                  AND rc.issue_category_code = :issue
                  AND ( :scale IS NULL OR rc.scale_level_code = :scale )
                  AND """ + _interval_active_at_year("rc.date_start", "rc.date_end") + """
                ORDER BY """ + _year_from_date_expr("rc.date_start") + """ DESC
                LIMIT 1
            ) AS strength,
            (
                SELECT rc.confidence_score
                FROM relationship_characterizations rc
                WHERE rc.relationship_id = rel.relationship_id
                  AND rc.issue_category_code = :issue
                  AND ( :scale IS NULL OR rc.scale_level_code = :scale )
                  AND """ + _interval_active_at_year("rc.date_start", "rc.date_end") + """
                ORDER BY """ + _year_from_date_expr("rc.date_start") + """ DESC
                LIMIT 1
            ) AS confidence_score,
            (
                SELECT rc.source_id
                FROM relationship_characterizations rc
                WHERE rc.relationship_id = rel.relationship_id
                  AND rc.issue_category_code = :issue
                  AND ( :scale IS NULL OR rc.scale_level_code = :scale )
                  AND """ + _interval_active_at_year("rc.date_start", "rc.date_end") + """
                ORDER BY """ + _year_from_date_expr("rc.date_start") + """ DESC
                LIMIT 1
            ) AS source_id,
            (
                SELECT rc.justification_note
                FROM relationship_characterizations rc
                WHERE rc.relationship_id = rel.relationship_id
                  AND rc.issue_category_code = :issue
                  AND ( :scale IS NULL OR rc.scale_level_code = :scale )
                  AND """ + _interval_active_at_year("rc.date_start", "rc.date_end") + """
                ORDER BY """ + _year_from_date_expr("rc.date_start") + """ DESC
                LIMIT 1
            ) AS justification_note
        FROM relationships rel
        WHERE """ + _interval_active_at_year("rel.start_date", "rel.end_date") + """;
        """

        cur = conn.execute(edges_sql, {"year": year, "issue": issue, "scale": scale})
        edges = [dict(r) for r in cur.fetchall()]

        # Normalize: if no characterization active, fall back to baseline
        for e in edges:
            if e.get("alignment_status_code") is None:
                e["alignment_status_code"] = e.get("baseline_alignment_status")
                e["strength"] = e.get("baseline_strength")
                e["source_id"] = e.get("baseline_source_id")
                e["confidence_score"] = None
                e["justification_note"] = None

        # Events (for timeline markers)
        events_sql = """
        SELECT
            event_id,
            event_name,
            event_type_code,
            start_date,
            end_date,
            description,
            place_id
        FROM events
        WHERE """ + _interval_active_at_year("start_date", "end_date") + """
        ORDER BY """ + _year_from_date_expr("start_date") + """;
        """

        cur = conn.execute(events_sql, {"year": year})
        events = [dict(r) for r in cur.fetchall()]

        # Sources referenced by nodes/edges
        source_ids = set()
        for n in nodes:
            if n.get("stance_source_id"):
                source_ids.add(n["stance_source_id"])
        for e in edges:
            if e.get("source_id"):
                source_ids.add(e["source_id"])

        sources: List[Dict[str, Any]] = []
        if source_ids:
            placeholders = ",".join(["?"] * len(source_ids))
            sources = db.fetch_all(
                conn,
                f"SELECT source_id, source_type_code, title, creator, date_created, archive, collection, box_folder, url, citation_full FROM sources WHERE source_id IN ({placeholders})",
                tuple(source_ids),
            )

    return {
        "year": year,
        "issue": issue,
        "scale": scale,
        "nodes": nodes,
        "edges": edges,
        "events": events,
        "sources": sources,
    }


@app.get("/api/health")
def health() -> Dict[str, Any]:
    db_path = db.default_db_path()
    return {"ok": True, "db_path": str(db_path), "db_exists": db_path.exists()}
