# UnionismNetwork

Early-stage dissertation research database for tracking South Carolina Unionists with uneven source coverage.

## Why this schema

This project starts from highly uneven evidence:

- rich records for a few elite figures
- sparse references for many non-elite figures

The database is designed to:

- capture partial records without forcing false precision
- preserve source provenance for every claim
- record uncertainty and archival silence explicitly
- scale as new people and documents are discovered

## Files

- [schema.sql](schema.sql): SQLite schema with constraints and indexes
- [seed_minimal.sql](seed_minimal.sql): optional starter lookup values
- [entry_template.sql](entry_template.sql): starter inserts including issue-specific relationship coding

## Quick start

1. Create the database:

```bash
sqlite3 unionism.db < schema.sql
```

2. (Optional) Load starter lookup values:

```bash
sqlite3 unionism.db < seed_minimal.sql
```

3. Open interactive mode:

```bash
sqlite3 unionism.db
```

Helpful shell commands:

```sql
.tables
.schema people
.headers on
.mode column
```

## Interactive web app (MVP)

This repo now includes a minimal local web app:

- FastAPI server that queries `unionism.db`
- linked Leaflet map + D3 network UI
- year slider (1817–1865) + issue selector + scale filter

### 1) Initialize a local SQLite database

Create `unionism.db` from the schema + lookup seeds:

```bash
./.venv/bin/python scripts/init_db.py
```

If `unionism.db` already exists, `init_db.py` will refuse to overwrite it unless you pass `--overwrite`.

### 1a) Keep an existing DB aligned with schema.sql

If you already have a populated `unionism.db` and you pull schema changes (new indexes/triggers), apply them idempotently:

```bash
./.venv/bin/python scripts/apply_schema.py
./.venv/bin/python scripts/audit_db.py
```

Optional (demo-only): load the MVP demo seed to get your Phase-1 roster + key places on the map immediately:

```bash
sqlite3 unionism.db < seed_mvp_demo.sql
```

Optional: load the example inserts in `entry_template.sql`:

```bash
sqlite3 unionism.db < entry_template.sql
```

### 1b) Load people extracted from your corpus (Keep/Merge workflow)

If you’ve manually edited the review file (actions `keep`/`merge`/`drop`/`review`) in
`data/staging/people_review_edited.csv`, regenerate the staging outputs and load them into the DB:

```bash
./.venv/bin/python scripts/apply_people_review.py --overwrite
./.venv/bin/python scripts/load_people_staging.py --dry-run
./.venv/bin/python scripts/load_people_staging.py
```

This inserts rows into `people` and `person_aliases` (re-using an existing person when names match).

To indicate that the imported people are connected to B. F. Perry via his letters corpus (a corpus-derived link, not a claim of direct relationship), generate `relationships` edges from BF Perry to every staged person:

```bash
./.venv/bin/python scripts/link_corpus_mentions.py
```

To add "mentioned with" connections (co-mentions in the same letter), generate aggregated co-mention edges from the PerryLetters database:

```bash
./.venv/bin/python scripts/link_co_mentions_from_perryletters.py
```

### 1c) Manually code issues over time (positions + relationship fracture)

For dissertation analysis, you’ll usually hand-enter issue stances and issue-specific relationship shifts, then bulk-load them.

If your `events` list is becoming your working “issue vocabulary” (e.g., you have rows like “Tariff of 1828”, “Nullification Crisis”, etc.), you can optionally promote those event names into selectable `issue_category_code` entries:

```bash
./.venv/bin/python scripts/seed_issue_categories_from_events.py
./.venv/bin/python scripts/seed_issue_categories_from_events.py --apply
```

1) Fill in `positions` (a person’s stance on an issue over an interval):

```bash
./.venv/bin/python scripts/load_positions_staging.py --dry-run
./.venv/bin/python scripts/load_positions_staging.py
```

Edit the staging file at `data/staging/positions_staging.csv`.

2) Fill in `relationship_characterizations` (alignment/fracture on an issue over an interval for a given tie):

```bash
./.venv/bin/python scripts/load_relationship_characterizations_staging.py --dry-run
./.venv/bin/python scripts/load_relationship_characterizations_staging.py
```

Edit the staging file at `data/staging/relationship_characterizations_staging.csv`.
If `relationship_id` is blank, the loader will create (or find) a baseline row in `relationships` for `(person_a, person_b, relationship_type_code)`.

### 1d) Add places, residences (map), and events (timeline)

These staging loaders help you build the time + regional scaffolding that your issue claims attach to:

```bash
./.venv/bin/python scripts/load_places_staging.py --dry-run
./.venv/bin/python scripts/load_places_staging.py

./.venv/bin/python scripts/load_residences_staging.py --dry-run
./.venv/bin/python scripts/load_residences_staging.py

./.venv/bin/python scripts/load_events_staging.py --dry-run
./.venv/bin/python scripts/load_events_staging.py
```

See `data/staging/MANUAL_CODING_EXAMPLES.md` for copy/paste starter rows.

### 2) Run the server

```bash
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Open:

- http://127.0.0.1:8000/

API endpoints:

- `GET /api/health`
- `GET /api/meta`
- `GET /api/state?year=1832&issue=nullification` (optional `scale=`)

## Suggested first workflow

1. Add a source in `sources`.
2. Add or update a person in `people`.
3. Add a dated claim in `positions` with confidence and evidence type.
4. Add relationships only when evidence supports them.
5. Use `person_aliases` for name variants found in archives.
6. Use `relationship_characterizations` to code issue-by-issue alignment shifts.

## Capturing Unionist fracture by issue

Use two layers together:

- `relationships`: the baseline tie between two actors (kinship, alliance, correspondence)
- `relationship_characterizations`: dated, issue-specific alignment for that same tie

This allows one pair to be aligned on one issue but strained or fractured on another, which is central to your dissertation argument.

## Minimum defensibility standard

For each interpretive claim in `positions`, fill these fields:

- `source_id`
- `claim_type`
- `confidence_score`
- `justification_note`

This keeps your analysis auditable as your corpus grows.
