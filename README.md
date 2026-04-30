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

Optional (demo-only): load the MVP demo seed to get your Phase-1 roster + key places on the map immediately:

```bash
sqlite3 unionism.db < seed_mvp_demo.sql
```

Optional: load the example inserts in `entry_template.sql`:

```bash
sqlite3 unionism.db < entry_template.sql
```

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
