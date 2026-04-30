# Methods & System Architecture (UnionismNetwork)

This document describes the **digital component** of the dissertation project “The Unionist South: The Persistence of Dissent in Antebellum South Carolina.” It is written to support academic defensibility: the system is designed so that **interpretive statements are stored as dated, sourced claims** and the visualization is a reproducible view over those claims.

## 1) Research Goal → Digital Method

### Research goal (what the tool is for)
The project visualizes:
- a **social network** of South Carolina Unionists and their ties,
- how relationships **strengthen/weaken** and **align/fracture** by **issue** and **scale** (local/state/regional/national),
- how these patterns change through time (MVP timeline: **1817–1865**), and
- how **regionality** (within South Carolina and beyond) shapes alignment, fracture, and information flow.

### Core methodological principle
The system separates:
- **data storage** (SQLite tables),
- **interpretive coding** (stances, alignments, strength, confidence, evidence type), and
- **views** (API queries + interactive visualization).

This ensures that the visualization does not “invent” interpretation at render time. Instead, it displays interpretations already recorded as claims.

## 2) System Overview (what exists in the repo)

### Components
1. **Database layer** — SQLite file `unionism.db` generated from the schema.
2. **API layer** — a local Python web server (FastAPI) that queries SQLite and returns JSON.
3. **Visualization layer** — a browser UI (HTML/CSS/JS) that requests JSON and renders:
   - a Leaflet-based map
   - a D3 force-directed network

### Why a local server?
The visualization is a web page that needs structured data. A local API server provides:
- a stable “contract” for what the visualization requests,
- centralized query logic (so one definition of “state at year Y”), and
- a single point of control for reproducibility (database snapshot + query parameters).

### Repository map (key files)
- `schema.sql` — canonical SQLite schema
- `seed_minimal.sql` — lookup table seeds
- `scripts/init_db.py` — creates `unionism.db` from `schema.sql` (+ optional seeds)
- `app/main.py` — FastAPI app (routes + query logic)
- `app/db.py` — SQLite connection helpers
- `app/static/index.html` — UI skeleton
- `app/static/app.js` — visualization logic (fetch state → render map/network/details)
- `app/static/styles.css` — basic styling
- `seed_mvp_demo.sql` — demo-only starter rows (placeholders; not evidence)

## 3) Data Model (SQLite) and Its Scholarly Rationale

The schema is designed for historical research constraints:
- uneven archival survival
- ambiguous or contested interpretation
- changes over time
- multiple scales (local/state/regional/national)

### 3.1 Entities (things)
- `people` — individuals in the network (elite and non-elite where possible)
- `places` — geographic nodes (town/county/state/region/nation) with optional lat/long and SC regional coding
- `events` — historical events with date ranges and optional place
- `organizations` + `person_organization` — institutional affiliation and roles
- `sources` — provenance: archives, citations, URLs, metadata

### 3.2 Claims (interpretations)
The schema models interpretation explicitly:

**A) Individual stances** — `positions`
Each row is a dated claim about an individual’s stance on an issue:
- `issue_category_code` (e.g., nullification, secession, slavery)
- `scale_level_code` (local/state/regional/national)
- numeric stance dimensions in `[-1, 1]`:
  - `stance_on_union`
  - `stance_on_states_rights`
  - `stance_on_slavery`
  - `stance_on_secession`
- `position_label_code` (human-readable category)
- defensibility fields:
  - `claim_type_code` (observed/inferred/contested)
  - `confidence_score` (1–3)
  - `evidence_type_code` (direct_quote/inferred/indirect_reference/mixed)
  - `counterevidence_present` (0/1)
  - `source_id` (required)
  - `justification_note` (required)

**B) Baseline relationships** — `relationships`
Each row is a base tie between two people:
- type (kinship, friendship, political_alliance, correspondence, etc.)
- date range + baseline strength
- a broad alignment status if appropriate

**C) Issue-specific relationship shifts** — `relationship_characterizations`
This is the key method for “nuance”:
- it attaches to a baseline `relationship_id`
- it adds *issue-specific*, dated alignment + strength
- it includes the same defensibility fields (claim type, confidence, evidence type, source, justification)

This structure supports historical arguments like:
> Two figures may be aligned on federal power but fractured on nullification, and those patterns can change over time.

### 3.3 Evidence / uncertainty as first-class data
The schema encodes uncertainty rather than hiding it:
- confidence scores and evidence types for each claim
- uneven record survival via `source_density_code` and `representation_depth_code` in `people`
- optional “erasure” flags to represent archival silence

## 4) Time Model (How “Change Over Time” Works)

### 4.1 Date representation
Dates are stored as TEXT (typically ISO-like `YYYY-MM-DD`) in:
- `positions.date_start`, `positions.date_end`
- `relationships.start_date`, `relationships.end_date`
- `relationship_characterizations.date_start`, `relationship_characterizations.date_end`
- `events.start_date`, `events.end_date`

### 4.2 MVP UI time step
The MVP UI is **year-by-year**. The API treats a record as “active” at year *Y* if:
- start year is `NULL` or `<= Y`, and
- end year is `NULL` or `>= Y`.

This allows:
- point claims (start date only) and
- interval claims (start + end)

to coexist.

### 4.3 Selecting “the stance at year Y”
An individual may have multiple claims about the same issue over time. The API selects:
- the most recent active claim by `date_start` year.

This is a design choice for the MVP to keep the visualization deterministic and explainable.

## 5) API Layer (FastAPI)

### 5.1 Why an API layer exists
The API defines the reproducible transformation from:
- **tables of claims** → **a visualization-ready JSON snapshot**.

This makes the “digital method” documentable as:
- input DB snapshot
- endpoint + parameters
- output JSON schema

### 5.2 Implemented endpoints
- `GET /` — serves the UI
- `GET /api/health` — reports DB path + whether it exists
- `GET /api/meta` — returns available issues/scales/people and the year range used by the UI
- `GET /api/state?year=YYYY&issue=CODE&scale=CODE?` — returns the visualization state for a specific year/issue

### 5.3 `/api/state` output schema (conceptual)
The endpoint returns:
- `nodes[]`: people with stance fields and (optional) map place
- `edges[]`: relationships with issue-specific characterization if present (fallback to baseline)
- `events[]`: events active at year Y
- `sources[]`: citations for any `source_id` referenced in nodes/edges (when present)

### 5.4 Query logic (interpretive rules)
The API follows these rules:

**Nodes**
- include all people in `people` (MVP)
- attach their stance for the selected `issue` at year `Y` if an active `positions` claim exists
- choose a map position by:
  1) an active `person_place_residence` row at year `Y` (most recent start), else
  2) `people.birth_place_id` (if present)

**Edges**
- include baseline `relationships` active at year `Y`
- for each relationship, if an active issue-specific `relationship_characterizations` exists at year `Y` (and optional `scale` filter), use it
- otherwise, fall back to the baseline relationship strength/alignment

**Evidence display**
- when a node/edge references `source_id`, the API includes those sources in `sources[]` so the UI can show citations.

## 6) Visualization Layer (Leaflet + D3)

### 6.1 Linked views
The UI is a single page with three synchronized panels:
1. **Map panel** (Leaflet)
   - plots people with a `map_place` that has lat/long
   - clicking a marker selects a person
2. **Network panel** (D3 force layout)
   - nodes are people
   - edges are baseline relationships with issue-specific overlays
   - edge color encodes alignment status
   - edge width encodes strength
   - clicking selects a person or an edge
3. **Details panel**
   - shows the selected person’s stance values and justification
   - shows the selected edge’s alignment/strength and justification
   - shows citation text when available

### 6.2 Rendering pipeline (UI)
On load:
1. UI requests `/api/meta` to populate dropdowns.
2. UI requests `/api/state` for the default year/issue.
3. UI renders map markers, network, and details.

On control changes (year/issue/scale):
1. UI requests a new `/api/state`.
2. UI re-renders the map and network.

### 6.3 Why the UI is thin
The UI does not determine “truth.” It only:
- requests a state snapshot
- visualizes it
- exposes evidence text and citations

This separation supports academic defensibility.

## 7) Reproducibility & Audit Trail

### 7.1 What must be archived for a dissertation figure
For any visualization state you cite, preserve:
- the exact database file used (`unionism.db` snapshot)
- the endpoint parameters:
  - `year`
  - `issue`
  - `scale` (if used)
- the returned JSON (optional but recommended)

This makes it possible to regenerate the figure.

### 7.2 Minimum defensibility standard (claims)
For each interpretive claim in `positions` and `relationship_characterizations`, fill:
- `source_id`
- `claim_type_code`
- `confidence_score`
- `justification_note`

### 7.3 Demo seed disclaimer
`seed_mvp_demo.sql` exists only so the UI shows nodes/places immediately. It contains placeholder citations and should not be treated as evidence.

## 8) Known Limitations (MVP)

- **Edges may be empty** until baseline `relationships` are entered (this is expected).
- **Stances may be null** until `positions` claims are entered.
- **Geography depends on lat/long** in `places` and on `person_place_residence` coverage.
- The MVP uses a **single selected issue** at a time; multi-issue overlays can be added later.
- The MVP currently uses **year parsing** from the first 4 characters of date strings; consistent ISO date formatting is recommended.

## 9) How This Relates to the PerryLetters Project

The PerryLetters project used:
- a SQLite database for corpus metadata/text
- a Flask app for query-driven pages, map visualizations, and correction workflows

This project differs in emphasis:
- it treats political stance and relationship nuance as explicit, sourced claims
- it prioritizes a stable “state at year Y” API for linked map+network visualization

Flask could also implement this architecture, but FastAPI provides:
- automatic OpenAPI documentation,
- built-in validation of query parameters,
- a clearer “API contract” for academic explanation.

## 10) How to Run (current repo)

1) Initialize DB from schema:
- `./.venv/bin/python scripts/init_db.py`

2) (Optional demo-only) seed minimal roster/places:
- `sqlite3 unionism.db < seed_mvp_demo.sql`

3) Run the server:
- `./.venv/bin/python -m uvicorn app.main:app --reload --port 8000`

4) Open:
- `http://127.0.0.1:8000/`

## 11) Suggested Next Steps (research-driven)

1. Replace demo seed with sourced entries:
   - add `sources`
   - add `positions` for the selected issue/timepoints
   - add baseline `relationships` then `relationship_characterizations`
2. Expand place coverage:
   - SC counties/districts and any out-of-state places needed for each actor’s biography
3. Add “correspondence layer” (optional):
   - populate `correspondence` and connect it to relationships to visualize information flow.
