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
- [app/](app/): FastAPI server + web UI (network visualization at `/`, data workbench at `/people` — see below)
- [scripts/](scripts/): one-time NER ingestion + initial bulk-load scripts (archived; see "Legacy workflows" below)

## Day-to-day workflow (recommended)

After the initial corpus load is done, **all editing happens in the web app**. The CSV staging files were the bootstrap mechanism, not the ongoing curation tool.

1. Run the server (see "Run the server" below).
2. Go to **`/people`** — the People Workbench (under construction; see "Planned" section).
3. From there you can:
   - Search/browse all people in the database
   - Add a new person (with live duplicate-detection warnings as you type)
   - Edit an existing person's biographical fields
   - Add/remove aliases inline
   - Add a Position (issue stance with required source + justification)
   - Add a Relationship to another person (with optional issue characterization)
   - Find duplicates and merge two records
   - Delete a person (with confirmation showing what dependent rows will cascade)
4. The map + network visualization at `/` reads the database live — reload to see your edits.

The CSV-based "Keep/Merge review" pipeline described under **Legacy workflows** is **no longer the right tool** for ongoing curation once people are already in the DB. Use it only for first-time ingestion of a brand-new corpus.

## Web app: People Workbench (`/people`)

> Status: **planned** — replaces the current `/entry` page. Will be built incrementally; while under construction the old `/entry` remains accessible.

### Goal

A single page where you can browse, search, add, edit, merge, and delete people, and where each person's positions and relationships are edited in context — no tab-switching, no out-of-date dropdowns, no separate Person/Position/Alias forms.

### Layout

Two-pane shell with a left sidebar for cross-domain navigation:

```
┌──────────┬──────────────────────┬─────────────────────────────┐
│ Sidebar  │ LEFT: People list    │ RIGHT: Editor pane          │
│          │                      │                             │
│ People   │  [+ New person]      │  (empty when nothing chosen)│
│ Sources  │  [Search _________]  │                             │
│ Events   │  [Filter ▾]          │  Selected person:           │
│ Network  │                      │   ▸ Bio (editable inline)   │
│          │  [scrollable list    │   ▸ Aliases [+ add]         │
│          │   of all people]     │   ▸ Positions [+ add]       │
│          │                      │   ▸ Relationships [+ add]   │
│          │                      │   [Save] [Delete] [Merge…]  │
└──────────┴──────────────────────┴─────────────────────────────┘
```

The shell also hosts `/sources` and `/events` workbenches under the same conventions (sidebar nav, list + editor), so you have a coherent place to add a source or event without leaving the people view. Sources and events can also be created on-the-fly from inside the Position/Relationship sub-forms via inline "+ New" modals.

### Design decisions

| Concern | Decision |
|---|---|
| Merge behavior | Combine all metadata into one record with no data loss. Default = blanks-only fill (target keeps its values, blanks are filled from the loser). When two records have conflicting non-blank values, an **Advanced merge** dialog opens with a side-by-side picker (target value / other value / write a third) for each conflicting field. Aliases, positions, relationships, mentions, and notes from the loser are reparented to the survivor; the loser record is removed only after its data has been transferred. |
| Delete behavior | A confirmation dialog shows the count of dependent rows (positions, relationships, aliases, etc.) that will cascade. A single **Confirm delete** button is required — no name-typing. Block-with-cascade is preferred over soft-delete; no `is_deleted` flag is added to the schema. |
| Scope of the workbench | One unified shell hosting **People**, **Sources**, **Events**, and **Network**. Each is a sub-workbench under the same sidebar, so you can switch contexts without losing your place. |
| Relationships | **Folded in** to the per-person editor. From person X's view, you click "+ Add relationship" and pick person Y. No separate standalone relationship tab. |

### Migration

While the workbench is being built:

- `/entry` continues to work but is considered deprecated.
- A banner on `/entry` will point users to `/people` once that page is functional.
- `/entry` is removed once the workbench covers all of its current capabilities.

### Editing positions over time

A person's positions are not overwritten as their views change — each shift is a new dated row. The workbench shows a person's full position history sorted by date, so when you add a new position you can see what's already coded. The network/map at `/` automatically picks the row active at the selected year, so sliding the year control surfaces ideological drift across the dataset.

Same pattern for relationship alignment over time: each fracture/realignment is a new `relationship_characterizations` row with its own date range. The renderer colors edges using whichever characterization is active at the chosen year.

## Legacy workflows (corpus ingestion, one-time)

The scripts under `scripts/` and the CSVs under `data/staging/` were used to bootstrap the database from NER output for the Perry and Petigru corpora. They are kept for reference and for ingesting **brand-new** corpora that have not yet been loaded.

**Do not** edit `data/staging/people_review_edited.csv` to update people who are already in `unionism.db` — those edits will not be applied (the loader is insert/match-only, not update). Use the People Workbench instead.

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

### 1b) Load people extracted from your corpus (Keep/Merge workflow — legacy, one-time)

> **Use this only for ingesting a brand-new corpus that has not been loaded before.**
> Do not edit `people_review_edited.csv` to update people already in the database — the loader will not apply those changes. Use the People Workbench at `/people` instead.

If you've manually edited the review file (actions `keep`/`merge`/`drop`/`review`) in
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

### 1c) Manually code issues over time (positions + relationship fracture — legacy bulk-load)

> Prefer the People Workbench at `/people` for hand-coding individual positions and relationship characterizations. Use the staging files below only when you have a large pre-existing CSV to bulk-load.

For dissertation analysis, you'll usually hand-enter issue stances and issue-specific relationship shifts, then bulk-load them.

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

> Use the People Workbench at `/people` for steps 1–6 once it is available. Until then, use the existing `/entry` page.

1. Add a source.
2. Add or update a person (with duplicate detection).
3. Add a dated position with confidence, evidence type, source, and justification.
4. Add relationships only when evidence supports them.
5. Use person aliases for name variants found in archives.
6. Add issue-specific relationship characterizations to code alignment shifts over time.

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
