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


@app.get("/entry")
def entry_page() -> FileResponse:
    return FileResponse(str(static_dir / "entry.html"))


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
            SELECT person_id, full_name, display_name, birth_year, death_year,
                   home_region_sc_code, occupation, notes
            FROM people
            ORDER BY COALESCE(display_name, full_name)
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
            SELECT position_id, issue_category_code, position_label_code,
                   date_start, date_end, scale_level_code,
                   stance_on_union, stance_on_states_rights, stance_on_slavery, stance_on_secession,
                   confidence_score, source_id, justification_note
            FROM positions
            WHERE person_id = ?
            ORDER BY date_start, position_id
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
