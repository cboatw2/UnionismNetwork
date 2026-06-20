from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db

APP_TITLE = "Unionism Network"


def _year_from_date_expr(col: str) -> str:
    # Dates are stored as TEXT (ISO-ish). We treat the first 4 chars as year.
    # If the value is NULL, year is NULL.
    return f"CAST(substr({col}, 1, 4) AS INTEGER)"


def _interval_active_at_year(start_col: str, end_col: str,
                              year_min_param: str = ":year_min",
                              year_max_param: str = ":year_max") -> str:
    """SQL fragment matching rows whose interval overlaps a year window.

    With year_min == year_max == Y this matches rows active at year Y (the
    original point-in-time semantics). With a wide window (e.g. -9999..9999)
    it matches every row regardless of date, enabling an "all years" view.
    """
    start_year = _year_from_date_expr(start_col)
    end_year = _year_from_date_expr(end_col)
    return (
        f"(({start_col} IS NULL) OR ({start_year} IS NOT NULL AND {start_year} <= {year_max_param})) "
        f"AND (({end_col} IS NULL) OR ({end_year} IS NOT NULL AND {end_year} >= {year_min_param}))"
    )


app = FastAPI(title=APP_TITLE)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(static_dir / "index.html"))


@app.get("/entry")
def entry_page() -> FileResponse:
    return FileResponse(str(static_dir / "entry.html"))


@app.get("/people")
def people_page() -> FileResponse:
    return FileResponse(str(static_dir / "people.html"))


@app.get("/events")
def events_page() -> FileResponse:
    return FileResponse(str(static_dir / "events.html"))


@app.get("/places")
def places_page() -> FileResponse:
    return FileResponse(str(static_dir / "places.html"))


@app.get("/organizations")
def organizations_page() -> FileResponse:
    return FileResponse(str(static_dir / "organizations.html"))


@app.get("/sources")
def sources_page() -> FileResponse:
    return FileResponse(str(static_dir / "sources.html"))

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
        "years": {"min": 1779, "max": 1865, "step": 1},
        "issues": issues,
        "scales": scales,
        "people": people,
    }


@app.get("/api/state")
def state(
    year: int = Query(..., ge=0, le=2100),
    issue: str = Query("nullification"),
    scale: Optional[str] = Query(None),
) -> Dict[str, Any]:
    # year == 0 is the sentinel for "all years" (no temporal filter).
    all_years = (year == 0)
    year_min = -9999 if all_years else year
    year_max = 9999 if all_years else year
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
            -- New schema (Phase 2): authoritative stance categorical + freeform notes.
            (
                SELECT pos.stance_code
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS stance_code,
            (
                SELECT pos.position_notes
                FROM positions pos
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC
                LIMIT 1
            ) AS position_notes,
            -- Primary source from position_sources junction for the active position row.
            (
                SELECT ps.source_id
                FROM positions pos
                JOIN position_sources ps ON ps.position_id = pos.position_id
                WHERE pos.person_id = p.person_id
                  AND pos.issue_category_code = :issue
                  AND """ + _interval_active_at_year("pos.date_start", "pos.date_end") + """
                  AND ps.source_role = 'primary'
                ORDER BY """ + _year_from_date_expr("pos.date_start") + """ DESC, ps.source_id
                LIMIT 1
            ) AS stance_source_id,
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

        cur = conn.execute(nodes_sql, {"year_min": year_min, "year_max": year_max, "issue": issue})
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

        cur = conn.execute(edges_sql, {"year_min": year_min, "year_max": year_max, "issue": issue, "scale": scale})
        edges = [dict(r) for r in cur.fetchall()]

        # Normalize: if no characterization active, fall back to baseline
        for e in edges:
            if e.get("alignment_status_code") is None:
                e["alignment_status_code"] = e.get("baseline_alignment_status")
                e["strength"] = e.get("baseline_strength")
                e["source_id"] = e.get("baseline_source_id")
                e["confidence_score"] = None
                e["justification_note"] = None

        # ------------------------------------------------------------------
        # Layered edges: one edge per (low, high) pair, carrying a layers[]
        # array. Layer kinds:
        #   - "relationship"       : explicit row in `relationships`
        #   - "shared_membership"  : co-membership in an organization at year
        #   - "co_residence"       : both have an active residence at the same
        #                            place at year
        # Top-level fields (alignment_status_code, strength, relationship_type_code,
        # source_id, justification_note, shared_orgs, shared_count, relationship_id)
        # are derived from the "primary" layer (relationship preferred) for
        # back-compat with existing frontend rendering.
        # ------------------------------------------------------------------

        from collections import defaultdict
        pair_layers: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

        # 1) Relationship layers from the rows we just fetched.
        for e in edges:
            low = min(e["source"], e["target"])
            high = max(e["source"], e["target"])
            pair_layers[(low, high)].append({
                "kind": "relationship",
                "relationship_id": e["relationship_id"],
                "relationship_type_code": e["relationship_type_code"],
                "alignment_status_code": e.get("alignment_status_code"),
                "strength": e.get("strength"),
                "source_id": e.get("source_id"),
                "justification_note": e.get("justification_note"),
                "confidence_score": e.get("confidence_score"),
            })

        # 2) Shared-membership layers (derived).
        shared_sql = """
        WITH active_membership AS (
            SELECT po.person_id, po.organization_id, o.name AS org_name
              FROM person_organization po
              JOIN organizations o ON o.organization_id = po.organization_id
             WHERE """ + _interval_active_at_year("po.date_start", "po.date_end") + """
        )
        SELECT
            a.person_id AS source,
            b.person_id AS target,
            GROUP_CONCAT(DISTINCT a.org_name) AS shared_orgs,
            COUNT(DISTINCT a.organization_id) AS shared_count
          FROM active_membership a
          JOIN active_membership b
            ON a.organization_id = b.organization_id
           AND a.person_id < b.person_id
         GROUP BY a.person_id, b.person_id;
        """
        cur = conn.execute(shared_sql, {"year_min": year_min, "year_max": year_max})
        for sr in cur.fetchall():
            sr = dict(sr)
            pair_layers[(sr["source"], sr["target"])].append({
                "kind": "shared_membership",
                "orgs": sr["shared_orgs"],
                "count": sr["shared_count"],
            })

        # 3) Co-residence layers (derived).
        co_residence_sql = """
        WITH active_residence AS (
            SELECT r.person_id, r.place_id, r.residence_type_code,
                   r.date_start, r.date_end,
                   pl.place_name
              FROM person_place_residence r
              JOIN places pl ON pl.place_id = r.place_id
             WHERE """ + _interval_active_at_year("r.date_start", "r.date_end") + """
        )
        SELECT a.person_id AS source, b.person_id AS target,
               a.place_id, a.place_name,
               a.date_start AS a_start, a.date_end AS a_end,
               b.date_start AS b_start, b.date_end AS b_end
          FROM active_residence a
          JOIN active_residence b
            ON a.place_id = b.place_id
           AND a.person_id < b.person_id;
        """
        cur = conn.execute(co_residence_sql, {"year_min": year_min, "year_max": year_max})
        # Multiple rows possible for one pair (different places). Group them.
        co_pair_places: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for cr in cur.fetchall():
            cr = dict(cr)
            co_pair_places[(cr["source"], cr["target"])].append({
                "place_id": cr["place_id"],
                "place_name": cr["place_name"],
            })
        for key, places_list in co_pair_places.items():
            pair_layers[key].append({
                "kind": "co_residence",
                "places": places_list,
                "place_name": ", ".join(p["place_name"] for p in places_list),
                "count": len(places_list),
            })

        # 4) Collapse pair_layers into one edge per pair.
        # When a pair has multiple "relationship" layers (e.g. an NER-derived
        # `co_mentioned` row plus a curated `political_alliance`), prefer the
        # most informative one as the primary so the curated alignment is what
        # the frontend renders. Preference order:
        #   (a) relationship layer whose type is NOT `co_mentioned` AND has a
        #       non-null alignment_status_code,
        #   (b) any relationship layer whose type is NOT `co_mentioned`,
        #   (c) any relationship layer with a non-null alignment_status_code,
        #   (d) the first relationship layer (back-compat),
        #   (e) the first layer of any kind.
        layered_edges: List[Dict[str, Any]] = []
        for (low, high), layers in pair_layers.items():
            rel_layers = [l for l in layers if l["kind"] == "relationship"]
            primary = (
                next((l for l in rel_layers
                      if l.get("relationship_type_code") != "co_mentioned"
                      and l.get("alignment_status_code") is not None), None)
                or next((l for l in rel_layers
                         if l.get("relationship_type_code") != "co_mentioned"), None)
                or next((l for l in rel_layers
                         if l.get("alignment_status_code") is not None), None)
                or (rel_layers[0] if rel_layers else None)
                or layers[0]
            )
            sm = next((l for l in layers if l["kind"] == "shared_membership"), None)
            cr_layer = next((l for l in layers if l["kind"] == "co_residence"), None)
            edge = {
                "edge_id": f"pair:{low}:{high}",
                "source": low,
                "target": high,
                "layers": layers,
                # Back-compat: surface "primary" layer fields at top level.
                "relationship_id": primary.get("relationship_id") or f"pair:{low}:{high}",
                "relationship_type_code": primary.get("relationship_type_code") or primary["kind"],
                "alignment_status_code": primary.get("alignment_status_code"),
                "strength": primary.get("strength")
                            or (sm.get("count") if sm else None)
                            or (cr_layer.get("count") if cr_layer else None),
                "source_id": primary.get("source_id"),
                "justification_note": primary.get("justification_note"),
                "confidence_score": primary.get("confidence_score"),
            }
            if sm:
                edge["shared_orgs"] = sm.get("orgs")
                edge["shared_count"] = sm.get("count")
            if cr_layer:
                edge["co_residence_place"] = cr_layer.get("place_name")
                edge["co_residence_count"] = cr_layer.get("count")
            layered_edges.append(edge)

        edges = layered_edges

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

        cur = conn.execute(events_sql, {"year_min": year_min, "year_max": year_max})
        events = [dict(r) for r in cur.fetchall()]

        # Sources referenced by nodes/edges (walk all layers per edge so the
        # frontend can resolve sources from any layer, not just the primary).
        source_ids = set()
        for n in nodes:
            if n.get("stance_source_id"):
                source_ids.add(n["stance_source_id"])
        for e in edges:
            if e.get("source_id"):
                source_ids.add(e["source_id"])
            for layer in e.get("layers", []):
                if layer.get("source_id"):
                    source_ids.add(layer["source_id"])

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


# ---------------------------------------------------------------------------
# Data-entry API: lookups, people, sources, positions
# ---------------------------------------------------------------------------

@app.get("/api/lookups")
def lookups() -> Dict[str, Any]:
    """Return all lookup tables the entry form needs."""
    tables = [
        ("race", "lkp_race", "race_code"),
        ("class_status", "lkp_class_status", "class_code"),
        ("source_type", "lkp_source_type", "source_type_code"),
        ("event_type", "lkp_event_type", "event_type_code"),
        ("relationship_type", "lkp_relationship_type", "relationship_type_code"),
        ("alignment_status", "lkp_alignment_status", "alignment_status_code"),
        ("issue_category", "lkp_issue_category", "issue_category_code"),
        ("position_label", "lkp_position_label", "position_label_code"),
        ("scale_level", "lkp_scale_level", "scale_level_code"),
        ("stance", "lkp_stance", "stance_code"),
        ("confidence_score", "lkp_confidence_score", "confidence_score"),
        ("evidence_type", "lkp_evidence_type", "evidence_type_code"),
        ("claim_type", "lkp_claim_type", "claim_type_code"),
        ("representation_depth", "lkp_representation_depth", "representation_depth_code"),
        ("source_density", "lkp_source_density", "source_density_code"),
        ("erasure_reason", "lkp_erasure_reason", "erasure_reason_code"),
        ("residence_type", "lkp_residence_type", "residence_type_code"),
        ("org_type", "lkp_org_type", "org_type_code"),
        ("place_type", "lkp_place_type", "place_type_code"),
        ("region_sc", "lkp_region_sc", "region_sc_code"),
    ]
    out: Dict[str, List[Dict[str, Any]]] = {}
    with db.get_conn() as conn:
        for key, table, code_col in tables:
            try:
                out[key] = db.fetch_all(
                    conn,
                    f"SELECT {code_col} AS code, label FROM {table} ORDER BY label",
                )
            except Exception:
                out[key] = []
    return out


@app.get("/api/people")
def list_people() -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        return db.fetch_all(
            conn,
            """
            SELECT
                p.person_id,
                p.full_name,
                p.display_name,
                p.birth_year,
                p.death_year,
                p.home_region_sc_code,
                p.occupation,
                p.notes,
                (SELECT COUNT(*) FROM person_aliases pa WHERE pa.person_id = p.person_id)    AS alias_count,
                (SELECT COUNT(*) FROM positions po WHERE po.person_id = p.person_id)         AS position_count,
                (SELECT COUNT(*) FROM relationships r
                   WHERE r.person_low_id = p.person_id OR r.person_high_id = p.person_id)    AS relationship_count
            FROM people p
            ORDER BY COALESCE(p.display_name, p.full_name)
            """,
        )


@app.get("/api/people/{person_id}")
def get_person(person_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            "SELECT * FROM people WHERE person_id = ?",
            (person_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Person not found")
        row["aliases"] = db.fetch_all(
            conn,
            "SELECT alias_id, alias_name, source_id, notes FROM person_aliases WHERE person_id = ? ORDER BY alias_name",
            (person_id,),
        )
        row["positions"] = db.fetch_all(
            conn,
            """
            SELECT pos.position_id, pos.issue_category_code, pos.position_label_code,
                   pos.date_start, pos.date_end, pos.scale_level_code,
                   pos.stance_code, pos.position_notes,
                   pos.event_id, e.event_name AS event_name,
                   (SELECT GROUP_CONCAT(ps.source_id || ':' || ps.source_role, '|')
                      FROM position_sources ps
                     WHERE ps.position_id = pos.position_id) AS sources_packed
            FROM positions pos
            LEFT JOIN events e ON e.event_id = pos.event_id
            WHERE pos.person_id = ?
            ORDER BY pos.date_start, pos.position_id
            """,
            (person_id,),
        )
        row["relationships"] = db.fetch_all(
            conn,
            """
            SELECT r.relationship_id,
                   r.person_low_id, r.person_high_id,
                   r.relationship_type_code, r.alignment_status_code,
                   r.start_date, r.end_date, r.strength,
                                      r.source_id, r.notes,
                   CASE WHEN r.person_low_id = ? THEN r.person_high_id ELSE r.person_low_id END AS other_person_id,
                   (SELECT COALESCE(p2.display_name, p2.full_name)
                      FROM people p2
                      WHERE p2.person_id = CASE WHEN r.person_low_id = ? THEN r.person_high_id ELSE r.person_low_id END
                   ) AS other_person_name
            FROM relationships r
            WHERE r.person_low_id = ? OR r.person_high_id = ?
            ORDER BY r.start_date, r.relationship_id
            """,
            (person_id, person_id, person_id, person_id),
        )
        row["memberships"] = db.fetch_all(
            conn,
            """
            SELECT po.person_org_id, po.organization_id, po.role,
                   po.date_start, po.date_end, po.source_id, po.notes,
                   o.name AS organization_name, o.org_type_code,
                   o.place_id, pl.place_name AS place_name,
                   o.start_date AS org_start_date, o.end_date AS org_end_date
            FROM person_organization po
            JOIN organizations o ON o.organization_id = po.organization_id
            LEFT JOIN places pl ON pl.place_id = o.place_id
            WHERE po.person_id = ?
            ORDER BY po.date_start, po.person_org_id
            """,
            (person_id,),
        )
        row["residences"] = db.fetch_all(
            conn,
            """
            SELECT r.residence_id, r.person_id, r.place_id, r.residence_type_code,
                   r.date_start, r.date_end, r.source_id, r.notes,
                   pl.place_name
            FROM person_place_residence r
            JOIN places pl ON pl.place_id = r.place_id
            WHERE r.person_id = ?
            ORDER BY r.date_start, r.residence_id
            """,
            (person_id,),
        )
        row["person_sources"] = db.fetch_all(
            conn,
            """
            SELECT ps.person_source_id, ps.source_id, ps.notes,
                   s.title, s.creator, s.date_created, s.source_type_code
            FROM person_sources ps
            JOIN sources s ON s.source_id = ps.source_id
            WHERE ps.person_id = ?
            ORDER BY s.title
            """,
            (person_id,),
        )
        return row


@app.get("/api/sources")
def list_sources() -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        return db.fetch_all(
            conn,
            """
            SELECT source_id, source_type_code, title, creator, date_created,
                   archive, collection, box_folder, url, citation_full, notes
            FROM sources
            ORDER BY source_id DESC
            """,
        )


@app.get("/api/events")
def list_events() -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        return db.fetch_all(
            conn,
            """
            SELECT e.event_id, e.event_name, e.event_type_code,
                   e.start_date, e.end_date, e.place_id, e.description,
                   pl.place_name AS place_name,
                   (SELECT COUNT(*) FROM relationship_characterizations rc
                      WHERE rc.event_id = e.event_id) AS characterization_count
            FROM events e
            LEFT JOIN places pl ON pl.place_id = e.place_id
            ORDER BY e.start_date, e.event_name
            """,
        )


@app.get("/api/events/{event_id}")
def get_event(event_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT e.*, pl.place_name AS place_name
            FROM events e
            LEFT JOIN places pl ON pl.place_id = e.place_id
            WHERE e.event_id = ?
            """,
            (event_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        row["characterizations"] = db.fetch_all(
            conn,
            """
            SELECT rc.relationship_characterization_id, rc.relationship_id,
                   rc.issue_category_code, rc.alignment_status_code,
                   rc.date_start, rc.date_end, rc.source_id, rc.justification_note,
                   r.person_low_id, r.person_high_id,
                   pl.full_name AS person_low_name,
                   ph.full_name AS person_high_name
            FROM relationship_characterizations rc
            JOIN relationships r ON r.relationship_id = rc.relationship_id
            JOIN people pl ON pl.person_id = r.person_low_id
            JOIN people ph ON ph.person_id = r.person_high_id
            WHERE rc.event_id = ?
            ORDER BY rc.date_start
            """,
            (event_id,),
        )
        return row


class EventIn(BaseModel):
    event_name: Optional[str] = None
    event_type_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    place_id: Optional[int] = None
    description: Optional[str] = None


@app.post("/api/events")
def create_event(body: EventIn) -> Dict[str, Any]:
    name = _none_if_blank(body.event_name)
    etype = _none_if_blank(body.event_type_code)
    if not name:
        raise HTTPException(status_code=400, detail="event_name is required")
    if not etype:
        raise HTTPException(status_code=400, detail="event_type_code is required")
    with db.get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO events (event_name, event_type_code, start_date, end_date, place_id, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    etype,
                    _none_if_blank(body.start_date),
                    _none_if_blank(body.end_date),
                    _none_if_blank(body.place_id),
                    _none_if_blank(body.description),
                ),
            )
            conn.commit()
            return db.fetch_one(conn, "SELECT * FROM events WHERE event_id = ?", (int(cur.lastrowid),))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.patch("/api/events/{event_id}")
def update_event(event_id: int, body: EventIn) -> Dict[str, Any]:
    fields = ["event_name", "event_type_code", "start_date", "end_date", "place_id", "description"]
    updates: Dict[str, Any] = {}
    for f in fields:
        v = getattr(body, f)
        if v is not None:
            updates[f] = _none_if_blank(v)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = ", ".join(f"{k} = ?" for k in updates.keys())
    vals = list(updates.values()) + [event_id]
    with db.get_conn() as conn:
        cur = conn.execute(f"UPDATE events SET {sets} WHERE event_id = ?", vals)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        conn.commit()
        return db.fetch_one(conn, "SELECT * FROM events WHERE event_id = ?", (event_id,))


@app.delete("/api/events/{event_id}")
def delete_event(event_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(conn, "SELECT event_id FROM events WHERE event_id = ?", (event_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        # event_id on positions / relationship_characterizations is nullable, so
        # NULL them out rather than blocking the delete.
        conn.execute("UPDATE relationship_characterizations SET event_id = NULL WHERE event_id = ?", (event_id,))
        conn.execute("UPDATE positions SET event_id = NULL WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        conn.commit()
        return {"deleted_event_id": event_id}


@app.get("/api/places")
def list_places() -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        return db.fetch_all(
            conn,
            """
            SELECT place_id, place_name, place_type_code, parent_place_id,
                   latitude, longitude, region_sc_code, modern_state, notes
            FROM places
            ORDER BY place_name
            """,
        )


@app.get("/api/places/{place_id}")
def get_place(place_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT p.*, par.place_name AS parent_place_name
            FROM places p
            LEFT JOIN places par ON par.place_id = p.parent_place_id
            WHERE p.place_id = ?
            """,
            (place_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Place not found")
        return row

@app.get("/api/places/{place_id}")
def get_place(place_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT p.*, par.place_name AS parent_place_name
            FROM places p
            LEFT JOIN places par ON par.place_id = p.parent_place_id
            WHERE p.place_id = ?
            """,
            (place_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Place not found")
        return row


class PlaceIn(BaseModel):
    place_name: Optional[str] = None
    place_type_code: Optional[str] = None
    parent_place_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region_sc_code: Optional[str] = None
    modern_state: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/places")
def create_place(body: PlaceIn) -> Dict[str, Any]:
    name = (body.place_name or "").strip()
    ptype = (body.place_type_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="place_name is required")
    if not ptype:
        raise HTTPException(status_code=400, detail="place_type_code is required")
    with db.get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO places (place_name, place_type_code, parent_place_id,
                                    latitude, longitude, region_sc_code, modern_state, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name, ptype,
                    body.parent_place_id,
                    body.latitude,
                    body.longitude,
                    _none_if_blank(body.region_sc_code),
                    _none_if_blank(body.modern_state),
                    _none_if_blank(body.notes),
                ),
            )
            conn.commit()
            return get_place(int(cur.lastrowid))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.patch("/api/places/{place_id}")
def update_place(place_id: int, body: PlaceIn) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    if body.place_name is not None:
        fields["place_name"] = body.place_name.strip() or None
    if body.place_type_code is not None:
        fields["place_type_code"] = body.place_type_code.strip() or None
    if body.parent_place_id is not None:
        fields["parent_place_id"] = body.parent_place_id
    if body.latitude is not None:
        fields["latitude"] = body.latitude
    if body.longitude is not None:
        fields["longitude"] = body.longitude
    if body.region_sc_code is not None:
        fields["region_sc_code"] = _none_if_blank(body.region_sc_code)
    if body.modern_state is not None:
        fields["modern_state"] = _none_if_blank(body.modern_state)
    if body.notes is not None:
        fields["notes"] = _none_if_blank(body.notes)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [place_id]
    with db.get_conn() as conn:
        cur = conn.execute(f"UPDATE places SET {sets} WHERE place_id = ?", vals)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Place not found")
        conn.commit()
        return get_place(place_id)


@app.delete("/api/places/{place_id}")
def delete_place(place_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(conn, "SELECT place_id FROM places WHERE place_id = ?", (place_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Place not found")
        try:
            conn.execute("DELETE FROM places WHERE place_id = ?", (place_id,))
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete: organizations, events, or residences still reference this place. Remove or reassign them first.",
            )
        return {"deleted_place_id": place_id}

def _none_if_blank(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class PersonIn(BaseModel):
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    race_code: Optional[str] = None
    gender: Optional[str] = None
    class_code: Optional[str] = None
    occupation: Optional[str] = None
    home_region_sc_code: Optional[str] = None
    enslaved_status: Optional[str] = None
    source_density_code: Optional[str] = None
    representation_depth_code: Optional[str] = None
    erasure_flag: int = 0
    erasure_reason_code: Optional[str] = None
    notes: Optional[str] = None


PERSON_FIELDS = [
    "full_name", "display_name", "birth_year", "death_year",
    "race_code", "gender", "class_code", "occupation",
    "home_region_sc_code", "enslaved_status",
    "source_density_code", "representation_depth_code",
    "erasure_flag", "erasure_reason_code", "notes",
]


def _normalize_name(name: Optional[str]) -> str:
    """Lowercase, collapse whitespace, strip most punctuation. Matches loader logic."""
    import re as _re
    n = (name or "").strip().lower().replace("\u2019", "'")
    n = _re.sub(r"\s+", " ", n)
    n = _re.sub(r"[^\w\s']", "", n)
    return n.strip()


def _find_person_matches(
    conn,
    *,
    full_name: Optional[str],
    display_name: Optional[str],
    birth_year: Optional[int],
    death_year: Optional[int],
) -> List[Dict[str, Any]]:
    """Find likely-duplicate people by normalized name match against
    people.full_name / people.display_name / person_aliases.alias_name.

    Returns rows from people, each annotated with `match_kind` and
    `matched_on` so the UI can show what triggered the match.
    """
    candidates: Dict[int, Dict[str, Any]] = {}

    needles = []
    for raw, kind in [(full_name, "full_name"), (display_name, "display_name")]:
        v = _normalize_name(raw)
        if v:
            needles.append((v, kind))

    if not needles:
        return []

    # 1) Match against people.full_name and people.display_name (normalize via Python).
    rows = conn.execute(
        "SELECT person_id, full_name, display_name, birth_year, death_year, occupation, home_region_sc_code, notes FROM people"
    ).fetchall()
    for r in rows:
        pid = int(r["person_id"])
        fn_norm = _normalize_name(r["full_name"])
        dn_norm = _normalize_name(r["display_name"])
        for needle, kind in needles:
            if needle and (needle == fn_norm or needle == dn_norm):
                cand = candidates.setdefault(pid, dict(r))
                cand["match_kind"] = "name"
                cand["matched_on"] = kind
                break

    # 2) Match against aliases.
    alias_rows = conn.execute(
        """
        SELECT pa.person_id, pa.alias_name, p.full_name, p.display_name,
               p.birth_year, p.death_year, p.occupation, p.home_region_sc_code, p.notes
        FROM person_aliases pa
        JOIN people p ON p.person_id = pa.person_id
        """
    ).fetchall()
    for r in alias_rows:
        pid = int(r["person_id"])
        if pid in candidates:
            continue
        alias_norm = _normalize_name(r["alias_name"])
        for needle, _kind in needles:
            if needle and needle == alias_norm:
                rec = {
                    "person_id": pid,
                    "full_name": r["full_name"],
                    "display_name": r["display_name"],
                    "birth_year": r["birth_year"],
                    "death_year": r["death_year"],
                    "occupation": r["occupation"],
                    "home_region_sc_code": r["home_region_sc_code"],
                    "notes": r["notes"],
                    "match_kind": "alias",
                    "matched_on": r["alias_name"],
                }
                candidates[pid] = rec
                break

    # Tag birth/death-year compatibility so the UI can show stronger matches.
    out: List[Dict[str, Any]] = []
    for cand in candidates.values():
        cb = cand.get("birth_year")
        cd = cand.get("death_year")
        year_conflict = False
        if birth_year is not None and cb is not None and int(birth_year) != int(cb):
            year_conflict = True
        if death_year is not None and cd is not None and int(death_year) != int(cd):
            year_conflict = True
        cand["year_conflict"] = bool(year_conflict)
        out.append(cand)

    # Sort: name matches first, then alias; non-conflicting years first.
    out.sort(key=lambda c: (
        0 if c["match_kind"] == "name" else 1,
        0 if not c["year_conflict"] else 1,
        int(c["person_id"]),
    ))
    return out


@app.post("/api/people/match")
def match_people(body: PersonIn) -> Dict[str, Any]:
    """Return likely-duplicate candidates for the submitted name (no inserts)."""
    if not (body.full_name or body.display_name):
        return {"candidates": []}
    with db.get_conn() as conn:
        cands = _find_person_matches(
            conn,
            full_name=body.full_name,
            display_name=body.display_name,
            birth_year=body.birth_year,
            death_year=body.death_year,
        )
    return {"candidates": cands}


@app.post("/api/people")
def create_person(body: PersonIn, force: bool = Query(False)) -> Dict[str, Any]:
    """Insert a new person.

    By default this performs a duplicate check by normalized name (against
    people.full_name, people.display_name, and person_aliases.alias_name).
    If matches exist, returns 409 with the candidate list — the client can then
    either call this endpoint again with ?force=true to insert anyway, or call
    PATCH /api/people/{id}/merge to fill blank fields on the existing record.
    """
    if not (body.full_name or body.display_name):
        raise HTTPException(status_code=400, detail="full_name or display_name is required")

    with db.get_conn() as conn:
        if not force:
            cands = _find_person_matches(
                conn,
                full_name=body.full_name,
                display_name=body.display_name,
                birth_year=body.birth_year,
                death_year=body.death_year,
            )
            if cands:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Possible duplicate(s) found.",
                        "candidates": cands,
                    },
                )

        values = [_none_if_blank(getattr(body, f)) for f in PERSON_FIELDS]
        placeholders = ",".join(["?"] * len(PERSON_FIELDS))
        cols = ",".join(PERSON_FIELDS)
        try:
            cur = conn.execute(f"INSERT INTO people ({cols}) VALUES ({placeholders})", values)
            conn.commit()
            new_id = int(cur.lastrowid)
            return db.fetch_one(conn, "SELECT * FROM people WHERE person_id = ?", (new_id,))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.patch("/api/people/{person_id}/merge")
def merge_into_person(person_id: int, body: PersonIn) -> Dict[str, Any]:
    """Fill NULL/empty fields on an existing person from `body`, never overwriting
    existing non-null values. Notes are appended (separated by a newline) rather
    than replaced.

    This is the "safe merge" path the dedupe UI uses when you choose to update an
    existing record instead of creating a duplicate.
    """
    with db.get_conn() as conn:
        existing = db.fetch_one(conn, "SELECT * FROM people WHERE person_id = ?", (person_id,))
        if not existing:
            raise HTTPException(status_code=404, detail="Person not found")

        merged: Dict[str, Any] = {}
        appended_notes = None
        for f in PERSON_FIELDS:
            incoming = _none_if_blank(getattr(body, f))
            current = existing.get(f)
            if f == "notes":
                # Append incoming notes onto existing notes (separator newline).
                if incoming and incoming not in (current or ""):
                    if current:
                        appended_notes = f"{current}\n--- added (merge) ---\n{incoming}"
                    else:
                        appended_notes = incoming
                continue
            if f == "erasure_flag":
                # Only escalate to 1 if incoming says so AND existing is 0.
                if incoming and int(incoming) == 1 and int(current or 0) == 0:
                    merged[f] = 1
                continue
            if current in (None, "") and incoming not in (None, ""):
                merged[f] = incoming

        if appended_notes is not None:
            merged["notes"] = appended_notes

        if not merged:
            return {
                **existing,
                "_merge_status": "no_changes",
                "_merge_message": "No new fields to merge; existing record already has values.",
            }

        sets = ", ".join(f"{k} = ?" for k in merged.keys())
        values = list(merged.values()) + [person_id]
        conn.execute(
            f"UPDATE people SET {sets}, updated_at = datetime('now') WHERE person_id = ?",
            values,
        )
        conn.commit()
        updated = db.fetch_one(conn, "SELECT * FROM people WHERE person_id = ?", (person_id,))
        return {
            **updated,
            "_merge_status": "merged",
            "_merge_fields": list(merged.keys()),
        }


@app.patch("/api/people/{person_id}")
def update_person(person_id: int, body: PersonIn) -> Dict[str, Any]:
    updatable = [
        "full_name", "display_name", "birth_year", "death_year",
        "race_code", "gender", "class_code", "occupation",
        "home_region_sc_code", "enslaved_status",
        "source_density_code", "representation_depth_code",
        "erasure_flag", "erasure_reason_code", "notes",
    ]
    sets = ", ".join(f"{f} = ?" for f in updatable)
    values = [_none_if_blank(getattr(body, f)) for f in updatable]
    values.append(person_id)
    with db.get_conn() as conn:
        cur = conn.execute(
            f"UPDATE people SET {sets}, updated_at = datetime('now') WHERE person_id = ?",
            values,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Person not found")
        conn.commit()
        return db.fetch_one(conn, "SELECT * FROM people WHERE person_id = ?", (person_id,))


@app.get("/api/people/{person_id}/dependents")
def person_dependents(person_id: int) -> Dict[str, Any]:
    """Return counts of rows in other tables that reference this person.

    Used by the People Workbench delete-confirmation dialog so the user can
    see what will cascade.
    """
    with db.get_conn() as conn:
        existing = db.fetch_one(conn, "SELECT person_id FROM people WHERE person_id = ?", (person_id,))
        if not existing:
            raise HTTPException(status_code=404, detail="Person not found")

        def count(sql: str, params=(person_id,)) -> int:
            row = conn.execute(sql, params).fetchone()
            return int(row[0]) if row else 0

        counts = {
            "aliases": count("SELECT COUNT(*) FROM person_aliases WHERE person_id = ?"),
            "positions": count("SELECT COUNT(*) FROM positions WHERE person_id = ?"),
            "relationships": count(
                "SELECT COUNT(*) FROM relationships WHERE person_low_id = ? OR person_high_id = ?",
                (person_id, person_id),
            ),
            "organization_memberships": count(
                "SELECT COUNT(*) FROM person_organization WHERE person_id = ?"
            ),
            "residences": count(
                "SELECT COUNT(*) FROM person_place_residence WHERE person_id = ?"
            ),
        }
        counts["total"] = sum(counts.values())
        return counts


@app.delete("/api/people/{person_id}")
def delete_person(person_id: int) -> Dict[str, Any]:
    """Delete a person and cascade through aliases, positions, relationships,
    organization memberships, residences (FK ON DELETE CASCADE handles these).

    The caller is expected to have shown a confirmation dialog with the output
    of GET /api/people/{id}/dependents first.
    """
    with db.get_conn() as conn:
        existing = db.fetch_one(conn, "SELECT person_id FROM people WHERE person_id = ?", (person_id,))
        if not existing:
            raise HTTPException(status_code=404, detail="Person not found")
        try:
            conn.execute("DELETE FROM people WHERE person_id = ?", (person_id,))
            conn.commit()
            return {"deleted_person_id": person_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Delete failed: {exc}")


class SourceIn(BaseModel):
    source_type_code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    creator: Optional[str] = None
    date_created: Optional[str] = None
    archive: Optional[str] = None
    collection: Optional[str] = None
    box_folder: Optional[str] = None
    url: Optional[str] = None
    citation_full: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/sources")
def create_source(body: SourceIn) -> Dict[str, Any]:
    fields = [
        "source_type_code", "title", "creator", "date_created",
        "archive", "collection", "box_folder", "url",
        "citation_full", "notes",
    ]
    values = [_none_if_blank(getattr(body, f)) for f in fields]
    placeholders = ",".join(["?"] * len(fields))
    cols = ",".join(fields)
    with db.get_conn() as conn:
        try:
            cur = conn.execute(f"INSERT INTO sources ({cols}) VALUES ({placeholders})", values)
            conn.commit()
            new_id = int(cur.lastrowid)
            return db.fetch_one(conn, "SELECT * FROM sources WHERE source_id = ?", (new_id,))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")

@app.get("/api/sources/{source_id}")
def get_source(source_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            "SELECT * FROM sources WHERE source_id = ?",
            (source_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Source not found")
        row["usages"] = db.fetch_all(
            conn,
            """
            SELECT COALESCE(p.display_name, p.full_name) AS person_name, p.person_id,
                   'position' AS usage_type, pos.position_label_code AS detail
            FROM positions pos
            JOIN people p ON p.person_id = pos.person_id
            WHERE pos.source_id = ?
            UNION ALL
            SELECT COALESCE(p.display_name, p.full_name), p.person_id,
                   'membership', o.name
            FROM person_organization po
            JOIN people p ON p.person_id = po.person_id
            JOIN organizations o ON o.organization_id = po.organization_id
            WHERE po.source_id = ?
            UNION ALL
            SELECT COALESCE(p.display_name, p.full_name), p.person_id,
                   'relationship', COALESCE(p2.display_name, p2.full_name)
            FROM relationships r
            JOIN people p ON p.person_id = r.person_low_id
            JOIN people p2 ON p2.person_id = r.person_high_id
            WHERE r.source_id = ?
            UNION ALL
            SELECT COALESCE(p.display_name, p.full_name), p.person_id,
                   'characterization', COALESCE(e.event_name, '(no event)')
            FROM relationship_characterizations rc
            JOIN relationships r ON r.relationship_id = rc.relationship_id
            JOIN people p ON p.person_id = r.person_low_id
            LEFT JOIN events e ON e.event_id = rc.event_id
            WHERE rc.source_id = ?
            ORDER BY person_name, usage_type
            """,
            (source_id, source_id, source_id, source_id),
        )
        return row


class SourceUpdate(BaseModel):
    source_type_code: Optional[str] = None
    title: Optional[str] = None
    creator: Optional[str] = None
    date_created: Optional[str] = None
    archive: Optional[str] = None
    collection: Optional[str] = None
    box_folder: Optional[str] = None
    url: Optional[str] = None
    citation_full: Optional[str] = None
    notes: Optional[str] = None


@app.patch("/api/sources/{source_id}")
def update_source(source_id: int, body: SourceUpdate) -> Dict[str, Any]:
    with db.get_conn() as conn:
        if not db.fetch_one(conn, "SELECT source_id FROM sources WHERE source_id = ?", (source_id,)):
            raise HTTPException(status_code=404, detail="Source not found")
        fields = [
            "source_type_code", "title", "creator", "date_created",
            "archive", "collection", "box_folder", "url", "citation_full", "notes",
        ]
        updates = {f: _none_if_blank(getattr(body, f)) for f in fields if getattr(body, f) is not None}
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE sources SET {set_clause} WHERE source_id = ?",
                (*updates.values(), source_id),
            )
            conn.commit()
    return get_source(source_id)


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        if not db.fetch_one(conn, "SELECT source_id FROM sources WHERE source_id = ?", (source_id,)):
            raise HTTPException(status_code=404, detail="Source not found")
        usage = db.fetch_one(
            conn,
            """
            SELECT (SELECT COUNT(*) FROM positions               WHERE source_id = ?)
                 + (SELECT COUNT(*) FROM relationships           WHERE source_id = ?)
                 + (SELECT COUNT(*) FROM person_organization     WHERE source_id = ?)
                 + (SELECT COUNT(*) FROM relationship_characterizations WHERE source_id = ?) AS total
            """,
            (source_id, source_id, source_id, source_id),
        )
        if usage and usage.get("total", 0) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Source referenced in {usage['total']} record(s). Remove references first.",
            )
        conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
        conn.commit()
        return {"deleted_source_id": source_id}

class PositionIn(BaseModel):
    person_id: int
    issue_category_code: str
    position_label_code: str
    scale_level_code: str
    claim_type_code: str
    confidence_score: int
    evidence_type_code: str
    source_id: int
    justification_note: str = Field(..., min_length=1)
    event_id: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    region_relevance_code: Optional[str] = None
    ideology_score: Optional[float] = None
    stance_on_union: Optional[float] = None
    stance_on_states_rights: Optional[float] = None
    stance_on_slavery: Optional[float] = None
    stance_on_secession: Optional[float] = None
    counterevidence_present: int = 0
    interpretive_note: Optional[str] = None
    # Phase 2 fields — drive the visualization clustering.
    stance_code: Optional[str] = None
    position_notes: Optional[str] = None


@app.post("/api/positions")
def create_position(body: PositionIn) -> Dict[str, Any]:
    fields = [
        "person_id", "event_id", "date_start", "date_end",
        "issue_category_code", "position_label_code", "ideology_score",
        "scale_level_code", "region_relevance_code",
        "stance_on_union", "stance_on_states_rights",
        "stance_on_slavery", "stance_on_secession",
        "claim_type_code", "confidence_score", "evidence_type_code",
        "counterevidence_present", "source_id",
        "justification_note", "interpretive_note",
        "stance_code", "position_notes",
    ]
    values = [_none_if_blank(getattr(body, f)) for f in fields]
    placeholders = ",".join(["?"] * len(fields))
    cols = ",".join(fields)
    with db.get_conn() as conn:
        try:
            cur = conn.execute(f"INSERT INTO positions ({cols}) VALUES ({placeholders})", values)
            conn.commit()
            new_id = int(cur.lastrowid)
            return db.fetch_one(conn, "SELECT * FROM positions WHERE position_id = ?", (new_id,))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.get("/api/positions/{position_id}")
def get_position(position_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT pos.*, e.event_name AS event_name
              FROM positions pos
              LEFT JOIN events e ON e.event_id = pos.event_id
             WHERE pos.position_id = ?
            """,
            (position_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")
        return row


class PositionUpdate(BaseModel):
    # Mirrors PositionIn minus person_id (positions don't move between people).
    # Legacy NOT NULL columns (claim_type_code, confidence_score, evidence_type_code,
    # source_id, justification_note) remain required during the Phase 1 dual-write
    # window — the edit dialog must round-trip them so values aren't lost.
    issue_category_code: str
    position_label_code: str
    scale_level_code: str
    claim_type_code: str
    confidence_score: int
    evidence_type_code: str
    source_id: int
    justification_note: str = Field(..., min_length=1)
    event_id: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    region_relevance_code: Optional[str] = None
    counterevidence_present: int = 0
    interpretive_note: Optional[str] = None
    # Phase 2 fields — drive the visualization clustering.
    stance_code: Optional[str] = None
    position_notes: Optional[str] = None


@app.patch("/api/positions/{position_id}")
def update_position(position_id: int, body: PositionUpdate) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn, "SELECT position_id FROM positions WHERE position_id = ?", (position_id,)
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Position not found")
        fields = [
            "issue_category_code", "position_label_code", "scale_level_code",
            "region_relevance_code",
            "claim_type_code", "confidence_score", "evidence_type_code",
            "counterevidence_present", "source_id",
            "justification_note", "interpretive_note",
            "stance_code", "position_notes",
            "event_id", "date_start", "date_end",
        ]
        values = [_none_if_blank(getattr(body, f)) for f in fields]
        set_clause = ", ".join(f"{f} = ?" for f in fields)
        try:
            conn.execute(
                f"UPDATE positions SET {set_clause} WHERE position_id = ?",
                values + [position_id],
            )
            conn.commit()
            return db.fetch_one(
                conn, "SELECT * FROM positions WHERE position_id = ?", (position_id,)
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Update failed: {exc}")


@app.delete("/api/positions/{position_id}")
def delete_position(position_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn, "SELECT position_id FROM positions WHERE position_id = ?", (position_id,)
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Position not found")
        # ON DELETE CASCADE on position_sources removes junction rows automatically.
        conn.execute("DELETE FROM positions WHERE position_id = ?", (position_id,))
        conn.commit()
        return {"deleted_position_id": position_id}


class AliasIn(BaseModel):
    person_id: int
    alias_name: str = Field(..., min_length=1)
    source_id: Optional[int] = None
    notes: Optional[str] = None


@app.post("/api/aliases")
def create_alias(body: AliasIn) -> Dict[str, Any]:
    with db.get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO person_aliases (person_id, alias_name, source_id, notes) VALUES (?, ?, ?, ?)",
                (body.person_id, body.alias_name.strip(), _none_if_blank(body.source_id), _none_if_blank(body.notes)),
            )
            conn.commit()
            new_id = int(cur.lastrowid)
            return db.fetch_one(conn, "SELECT * FROM person_aliases WHERE alias_id = ?", (new_id,))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


class RelationshipIn(BaseModel):
    # Relationships row
    person_a_id: int
    person_b_id: int
    relationship_type_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strength: Optional[int] = None
    alignment_status_code: Optional[str] = None
    source_id: Optional[int] = None
    notes: Optional[str] = None

    # Optional issue-specific characterization (all-or-nothing).
    # If issue_category_code is supplied, the rest of the required characterization
    # fields must also be supplied.
    issue_category_code: Optional[str] = None
    char_alignment_status_code: Optional[str] = None
    char_scale_level_code: Optional[str] = None
    char_event_id: Optional[int] = None
    char_date_start: Optional[str] = None
    char_date_end: Optional[str] = None
    char_strength: Optional[int] = None
    char_claim_type_code: Optional[str] = None
    char_confidence_score: Optional[int] = None
    char_evidence_type_code: Optional[str] = None
    char_counterevidence_present: int = 0
    char_source_id: Optional[int] = None
    char_justification_note: Optional[str] = None
    char_notes: Optional[str] = None


@app.post("/api/relationships")
def create_relationship(body: RelationshipIn) -> Dict[str, Any]:
    if body.person_a_id == body.person_b_id:
        raise HTTPException(status_code=400, detail="person_a_id and person_b_id must differ")

    # Enforce person_low_id < person_high_id per CHECK constraint.
    low_id, high_id = sorted([body.person_a_id, body.person_b_id])

    want_char = _none_if_blank(body.issue_category_code) is not None
    if want_char:
        required = {
            "char_alignment_status_code": body.char_alignment_status_code,
            "char_claim_type_code": body.char_claim_type_code,
            "char_confidence_score": body.char_confidence_score,
            "char_evidence_type_code": body.char_evidence_type_code,
            "char_source_id": body.char_source_id,
            "char_justification_note": _none_if_blank(body.char_justification_note),
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Issue characterization requires: {', '.join(missing)}",
            )

    with db.get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO relationships
                  (person_low_id, person_high_id, relationship_type_code,
                   start_date, end_date, strength, alignment_status_code,
                   source_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    low_id,
                    high_id,
                    body.relationship_type_code,
                    _none_if_blank(body.start_date),
                    _none_if_blank(body.end_date),
                    _none_if_blank(body.strength),
                    _none_if_blank(body.alignment_status_code),
                    _none_if_blank(body.source_id),
                    _none_if_blank(body.notes),
                ),
            )
            relationship_id = int(cur.lastrowid)

            char_id = None
            if want_char:
                cur2 = conn.execute(
                    """
                    INSERT INTO relationship_characterizations
                      (relationship_id, event_id, date_start, date_end,
                       issue_category_code, scale_level_code,
                       alignment_status_code, strength,
                       claim_type_code, confidence_score, evidence_type_code,
                       counterevidence_present, source_id,
                       justification_note, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        relationship_id,
                        _none_if_blank(body.char_event_id),
                        _none_if_blank(body.char_date_start),
                        _none_if_blank(body.char_date_end),
                        body.issue_category_code,
                        _none_if_blank(body.char_scale_level_code),
                        body.char_alignment_status_code,
                        _none_if_blank(body.char_strength),
                        body.char_claim_type_code,
                        body.char_confidence_score,
                        body.char_evidence_type_code,
                        1 if body.char_counterevidence_present else 0,
                        body.char_source_id,
                        body.char_justification_note,
                        _none_if_blank(body.char_notes),
                    ),
                )
                char_id = int(cur2.lastrowid)

            conn.commit()
            rel = db.fetch_one(
                conn,
                "SELECT * FROM relationships WHERE relationship_id = ?",
                (relationship_id,),
            )
            return {"relationship": rel, "characterization_id": char_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


# ----- Relationship inspection / characterization editor -----

@app.get("/api/relationships/{relationship_id}")
def get_relationship(relationship_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT r.*,
                   pl.full_name AS person_low_name,
                   ph.full_name AS person_high_name
            FROM relationships r
            JOIN people pl ON pl.person_id = r.person_low_id
            JOIN people ph ON ph.person_id = r.person_high_id
            WHERE r.relationship_id = ?
            """,
            (relationship_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Relationship not found")
        row["characterizations"] = db.fetch_all(
            conn,
            """
            SELECT rc.*, e.event_name AS event_name
            FROM relationship_characterizations rc
            LEFT JOIN events e ON e.event_id = rc.event_id
            WHERE rc.relationship_id = ?
            ORDER BY rc.date_start, rc.relationship_characterization_id
            """,
            (relationship_id,),
        )
        return row


@app.delete("/api/relationships/{relationship_id}")
def delete_relationship(relationship_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(conn, "SELECT relationship_id FROM relationships WHERE relationship_id = ?", (relationship_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Relationship not found")
        # ON DELETE CASCADE removes its characterizations.
        conn.execute("DELETE FROM relationships WHERE relationship_id = ?", (relationship_id,))
        conn.commit()
        return {"deleted_relationship_id": relationship_id}


class RelationshipUpdate(BaseModel):
    relationship_type_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strength: Optional[int] = None
    alignment_status_code: Optional[str] = None
    source_id: Optional[int] = None
    notes: Optional[str] = None


@app.patch("/api/relationships/{relationship_id}")
def update_relationship(relationship_id: int, body: RelationshipUpdate) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(conn, "SELECT relationship_id FROM relationships WHERE relationship_id = ?", (relationship_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Relationship not found")
        try:
            conn.execute(
                """
                UPDATE relationships SET
                  relationship_type_code = ?,
                  start_date = ?, end_date = ?,
                  strength = ?, alignment_status_code = ?,
                  source_id = ?, notes = ?
                WHERE relationship_id = ?
                """,
                (
                    body.relationship_type_code,
                    _none_if_blank(body.start_date),
                    _none_if_blank(body.end_date),
                    body.strength,
                    _none_if_blank(body.alignment_status_code),
                    body.source_id,
                    _none_if_blank(body.notes),
                    relationship_id,
                ),
            )
            conn.commit()
            return db.fetch_one(conn, "SELECT * FROM relationships WHERE relationship_id = ?", (relationship_id,))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Update failed: {exc}")


class CharacterizationIn(BaseModel):
    event_id: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    issue_category_code: str
    scale_level_code: Optional[str] = None
    alignment_status_code: str
    strength: Optional[int] = None
    claim_type_code: str
    confidence_score: int
    evidence_type_code: str
    counterevidence_present: int = 0
    source_id: int
    justification_note: str
    notes: Optional[str] = None


@app.post("/api/relationships/{relationship_id}/characterizations")
def create_characterization(relationship_id: int, body: CharacterizationIn) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(conn, "SELECT relationship_id FROM relationships WHERE relationship_id = ?", (relationship_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Relationship not found")
        try:
            cur = conn.execute(
                """
                INSERT INTO relationship_characterizations
                  (relationship_id, event_id, date_start, date_end,
                   issue_category_code, scale_level_code,
                   alignment_status_code, strength,
                   claim_type_code, confidence_score, evidence_type_code,
                   counterevidence_present, source_id,
                   justification_note, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship_id,
                    _none_if_blank(body.event_id),
                    _none_if_blank(body.date_start),
                    _none_if_blank(body.date_end),
                    body.issue_category_code,
                    _none_if_blank(body.scale_level_code),
                    body.alignment_status_code,
                    _none_if_blank(body.strength),
                    body.claim_type_code,
                    body.confidence_score,
                    body.evidence_type_code,
                    1 if body.counterevidence_present else 0,
                    body.source_id,
                    body.justification_note,
                    _none_if_blank(body.notes),
                ),
            )
            conn.commit()
            return db.fetch_one(
                conn,
                "SELECT * FROM relationship_characterizations WHERE relationship_characterization_id = ?",
                (int(cur.lastrowid),),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.delete("/api/characterizations/{characterization_id}")
def delete_characterization(characterization_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            "SELECT relationship_characterization_id FROM relationship_characterizations WHERE relationship_characterization_id = ?",
            (characterization_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Characterization not found")
        conn.execute(
            "DELETE FROM relationship_characterizations WHERE relationship_characterization_id = ?",
            (characterization_id,),
        )
        conn.commit()
        return {"deleted_characterization_id": characterization_id}


# ============================================================================
# Phase 3: Organizations (civic / religious / political clubs) + memberships
# ============================================================================

class OrganizationIn(BaseModel):
    name: str
    org_type_code: Optional[str] = None
    place_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None


class MembershipIn(BaseModel):
    organization_id: int
    role: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    source_id: Optional[int] = None
    notes: Optional[str] = None
    # Optional geographic tie. If provided we (a) insert a person_place_residence
    # row for the same person/place/dates and (b) backfill the organization's
    # place_id when it is currently null.
    place_id: Optional[int] = None
    residence_type_code: Optional[str] = "temporary_residence"


@app.get("/api/organizations")
def list_organizations() -> List[Dict[str, Any]]:
    with db.get_conn() as conn:
        return db.fetch_all(
            conn,
            """
            SELECT o.organization_id, o.name, o.org_type_code, o.place_id,
                   o.start_date, o.end_date, o.notes,
                   pl.place_name AS place_name,
                   (SELECT COUNT(*) FROM person_organization po
                      WHERE po.organization_id = o.organization_id) AS member_count
            FROM organizations o
            LEFT JOIN places pl ON pl.place_id = o.place_id
            ORDER BY o.name
            """,
        )


@app.get("/api/organizations/{organization_id}")
def get_organization(organization_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT o.*, pl.place_name AS place_name
            FROM organizations o
            LEFT JOIN places pl ON pl.place_id = o.place_id
            WHERE o.organization_id = ?
            """,
            (organization_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        row["members"] = db.fetch_all(
            conn,
            """
            SELECT po.person_org_id, po.person_id, po.organization_id, po.role,
                   po.date_start, po.date_end, po.source_id, po.notes,
                   COALESCE(p.display_name, p.full_name) AS person_name
            FROM person_organization po
            JOIN people p ON p.person_id = po.person_id
            WHERE po.organization_id = ?
            ORDER BY po.date_start, po.person_org_id
            """,
            (organization_id,),
        )
        return row


@app.post("/api/organizations")
def create_organization(body: OrganizationIn) -> Dict[str, Any]:
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    with db.get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO organizations (name, org_type_code, place_id, start_date, end_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    body.name.strip(),
                    body.org_type_code,
                    body.place_id,
                    body.start_date,
                    body.end_date,
                    body.notes,
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=400, detail=f"Insert failed: {e}")
        return get_organization(new_id)


@app.patch("/api/organizations/{organization_id}")
def update_organization(organization_id: int, body: OrganizationIn) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn,
            "SELECT organization_id FROM organizations WHERE organization_id = ?",
            (organization_id,),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Organization not found")
        conn.execute(
            """
            UPDATE organizations SET
              name = ?, org_type_code = ?, place_id = ?,
              start_date = ?, end_date = ?, notes = ?
            WHERE organization_id = ?
            """,
            (
                body.name.strip(),
                body.org_type_code,
                body.place_id,
                body.start_date,
                body.end_date,
                body.notes,
                organization_id,
            ),
        )
        conn.commit()
    return get_organization(organization_id)


@app.delete("/api/organizations/{organization_id}")
def delete_organization(organization_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn,
            "SELECT organization_id FROM organizations WHERE organization_id = ?",
            (organization_id,),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Organization not found")
        # Drop memberships explicitly (no ON DELETE CASCADE assumed).
        conn.execute(
            "DELETE FROM person_organization WHERE organization_id = ?",
            (organization_id,),
        )
        conn.execute(
            "DELETE FROM organizations WHERE organization_id = ?",
            (organization_id,),
        )
        conn.commit()
        return {"deleted_organization_id": organization_id}


@app.post("/api/people/{person_id}/memberships")
def add_membership(person_id: int, body: MembershipIn) -> Dict[str, Any]:
    with db.get_conn() as conn:
        person = db.fetch_one(
            conn, "SELECT person_id FROM people WHERE person_id = ?", (person_id,)
        )
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        org = db.fetch_one(
            conn,
            "SELECT organization_id, place_id FROM organizations WHERE organization_id = ?",
            (body.organization_id,),
        )
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        # Validate place if provided.
        if body.place_id is not None:
            place = db.fetch_one(
                conn,
                "SELECT place_id FROM places WHERE place_id = ?",
                (body.place_id,),
            )
            if not place:
                raise HTTPException(status_code=404, detail="Place not found")
        try:
            cur = conn.execute(
                """
                INSERT INTO person_organization
                  (person_id, organization_id, role, date_start, date_end, source_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    body.organization_id,
                    body.role,
                    body.date_start,
                    body.date_end,
                    body.source_id,
                    body.notes,
                ),
            )
            new_id = cur.lastrowid

            # Geographic tie: residence row for this person at this place + dates.
            residence_id: Optional[int] = None
            if body.place_id is not None:
                rcur = conn.execute(
                    """
                    INSERT INTO person_place_residence
                      (person_id, place_id, residence_type_code,
                       date_start, date_end, source_id, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        person_id,
                        body.place_id,
                        body.residence_type_code or "temporary_residence",
                        body.date_start,
                        body.date_end,
                        body.source_id,
                        f"via membership in organization {body.organization_id}",
                    ),
                )
                residence_id = rcur.lastrowid
                # Backfill the organization's place_id if it had none.
                if org["place_id"] is None:
                    conn.execute(
                        "UPDATE organizations SET place_id = ? WHERE organization_id = ?",
                        (body.place_id, body.organization_id),
                    )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=400, detail=f"Insert failed: {e}")
        row = db.fetch_one(
            conn,
            """
            SELECT po.person_org_id, po.person_id, po.organization_id, po.role,
                   po.date_start, po.date_end, po.source_id, po.notes,
                   o.name AS organization_name, o.org_type_code, o.place_id,
                   pl.place_name AS place_name
            FROM person_organization po
            JOIN organizations o ON o.organization_id = po.organization_id
            LEFT JOIN places pl ON pl.place_id = o.place_id
            WHERE po.person_org_id = ?
            """,
            (new_id,),
        )
        if residence_id is not None:
            row["residence_id"] = residence_id
        return row


@app.delete("/api/memberships/{person_org_id}")
def delete_membership(person_org_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn,
            "SELECT person_org_id FROM person_organization WHERE person_org_id = ?",
            (person_org_id,),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Membership not found")
        conn.execute(
            "DELETE FROM person_organization WHERE person_org_id = ?",
            (person_org_id,),
        )
        conn.commit()
        return {"deleted_person_org_id": person_org_id}


@app.get("/api/memberships/{person_org_id}")
def get_membership(person_org_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT po.person_org_id, po.person_id, po.organization_id, po.role,
                   po.date_start, po.date_end, po.source_id, po.notes,
                   o.name AS organization_name, o.org_type_code, o.place_id,
                   pl.place_name AS place_name,
                   COALESCE(p.display_name, p.full_name) AS person_name
              FROM person_organization po
              JOIN organizations o ON o.organization_id = po.organization_id
              JOIN people p ON p.person_id = po.person_id
              LEFT JOIN places pl ON pl.place_id = o.place_id
             WHERE po.person_org_id = ?
            """,
            (person_org_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Membership not found")
        return row


class MembershipUpdate(BaseModel):
    # Allow re-targeting the organization (e.g., when fixing a wrong pick) plus
    # the descriptive metadata. Geography is intentionally excluded — residences
    # are managed in their own section/endpoints.
    organization_id: int
    role: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    source_id: Optional[int] = None
    notes: Optional[str] = None


@app.patch("/api/memberships/{person_org_id}")
def update_membership(person_org_id: int, body: MembershipUpdate) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn,
            "SELECT person_org_id FROM person_organization WHERE person_org_id = ?",
            (person_org_id,),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Membership not found")
        org = db.fetch_one(
            conn,
            "SELECT organization_id FROM organizations WHERE organization_id = ?",
            (body.organization_id,),
        )
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        try:
            conn.execute(
                """
                UPDATE person_organization SET
                  organization_id = ?,
                  role = ?,
                  date_start = ?, date_end = ?,
                  source_id = ?,
                  notes = ?
                WHERE person_org_id = ?
                """,
                (
                    body.organization_id,
                    _none_if_blank(body.role),
                    _none_if_blank(body.date_start),
                    _none_if_blank(body.date_end),
                    body.source_id,
                    _none_if_blank(body.notes),
                    person_org_id,
                ),
            )
            conn.commit()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Update failed: {exc}")
    return get_membership(person_org_id)


class ResidenceIn(BaseModel):
    place_id: int
    residence_type_code: Optional[str] = "household"
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    source_id: Optional[int] = None
    notes: Optional[str] = None


@app.post("/api/people/{person_id}/residences")
def add_residence(person_id: int, body: ResidenceIn) -> Dict[str, Any]:
    with db.get_conn() as conn:
        person = db.fetch_one(conn, "SELECT person_id FROM people WHERE person_id = ?", (person_id,))
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        try:
            cur = conn.execute(
                """
                INSERT INTO person_place_residence
                  (person_id, place_id, residence_type_code,
                   date_start, date_end, source_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    body.place_id,
                    body.residence_type_code or "household",
                    _none_if_blank(body.date_start),
                    _none_if_blank(body.date_end),
                    body.source_id,
                    _none_if_blank(body.notes),
                ),
            )
            new_id = int(cur.lastrowid)
            conn.commit()
            return db.fetch_one(
                conn,
                """
                SELECT r.*, pl.place_name FROM person_place_residence r
                JOIN places pl ON pl.place_id = r.place_id
                WHERE r.residence_id = ?
                """,
                (new_id,),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.delete("/api/residences/{residence_id}")
def delete_residence(residence_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(conn, "SELECT residence_id FROM person_place_residence WHERE residence_id = ?", (residence_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Residence not found")
        conn.execute("DELETE FROM person_place_residence WHERE residence_id = ?", (residence_id,))
        conn.commit()
        return {"deleted_residence_id": residence_id}


@app.get("/api/residences/{residence_id}")
def get_residence(residence_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            """
            SELECT r.residence_id, r.person_id, r.place_id, r.residence_type_code,
                   r.date_start, r.date_end, r.source_id, r.notes,
                   pl.place_name AS place_name,
                   COALESCE(p.display_name, p.full_name) AS person_name
              FROM person_place_residence r
              JOIN people p ON p.person_id = r.person_id
              JOIN places pl ON pl.place_id = r.place_id
             WHERE r.residence_id = ?
            """,
            (residence_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Residence not found")
        return row


class ResidenceUpdate(BaseModel):
    place_id: int
    residence_type_code: Optional[str] = "household"
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    source_id: Optional[int] = None
    notes: Optional[str] = None


@app.patch("/api/residences/{residence_id}")
def update_residence(residence_id: int, body: ResidenceUpdate) -> Dict[str, Any]:
    with db.get_conn() as conn:
        existing = db.fetch_one(
            conn,
            "SELECT residence_id FROM person_place_residence WHERE residence_id = ?",
            (residence_id,),
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Residence not found")
        place = db.fetch_one(
            conn, "SELECT place_id FROM places WHERE place_id = ?", (body.place_id,)
        )
        if not place:
            raise HTTPException(status_code=404, detail="Place not found")
        try:
            conn.execute(
                """
                UPDATE person_place_residence SET
                  place_id = ?,
                  residence_type_code = ?,
                  date_start = ?, date_end = ?,
                  source_id = ?,
                  notes = ?
                WHERE residence_id = ?
                """,
                (
                    body.place_id,
                    body.residence_type_code or "household",
                    _none_if_blank(body.date_start),
                    _none_if_blank(body.date_end),
                    body.source_id,
                    _none_if_blank(body.notes),
                    residence_id,
                ),
            )
            conn.commit()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Update failed: {exc}")
    return get_residence(residence_id)


# ============================================================================
# Person Sources
# ============================================================================

class PersonSourceIn(BaseModel):
    source_id: int
    notes: Optional[str] = None


@app.post("/api/people/{person_id}/sources")
def add_person_source(person_id: int, body: PersonSourceIn) -> Dict[str, Any]:
    with db.get_conn() as conn:
        person = db.fetch_one(conn, "SELECT person_id FROM people WHERE person_id = ?", (person_id,))
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        source = db.fetch_one(conn, "SELECT source_id FROM sources WHERE source_id = ?", (body.source_id,))
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        try:
            cur = conn.execute(
                "INSERT INTO person_sources (person_id, source_id, notes) VALUES (?, ?, ?)",
                (person_id, body.source_id, _none_if_blank(body.notes)),
            )
            new_id = int(cur.lastrowid)
            conn.commit()
            return db.fetch_one(
                conn,
                """
                SELECT ps.person_source_id, ps.source_id, ps.notes,
                       s.title, s.creator, s.date_created, s.source_type_code
                FROM person_sources ps
                JOIN sources s ON s.source_id = ps.source_id
                WHERE ps.person_source_id = ?
                """,
                (new_id,),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Insert failed: {exc}")


@app.delete("/api/person_sources/{person_source_id}")
def delete_person_source(person_source_id: int) -> Dict[str, Any]:
    with db.get_conn() as conn:
        row = db.fetch_one(
            conn,
            "SELECT person_source_id FROM person_sources WHERE person_source_id = ?",
            (person_source_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail="Person source link not found")
        conn.execute("DELETE FROM person_sources WHERE person_source_id = ?", (person_source_id,))
        conn.commit()
        return {"deleted_person_source_id": person_source_id}
