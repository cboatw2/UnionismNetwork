# Manual coding examples (copy/paste)

These are example rows you can copy into the staging CSVs.

Important: the loaders accept either numeric IDs (recommended) or exact names (must match `full_name` or `display_name`).

## People metadata (record survival / completeness)

These fields live on `people` and are meant to *encode uneven archival survival* rather than hide it.

- `source_density_code` → FK to `lkp_source_density` (seeded: `high`, `medium`, `low`)
- `representation_depth_code` → FK to `lkp_representation_depth` (seeded: `full`, `partial`, `fragmentary`)

Suggested interpretation (you can adjust your own rubric):

- `full`: substantial direct record (letters, speeches, diaries, etc.) enabling richer claims
- `partial`: some direct record, but with notable gaps
- `fragmentary`: mostly indirect mention / sparse record; claims should be lower-confidence or narrower

To see current codes/labels in your DB:

```bash
sqlite3 unionism.db "SELECT * FROM lkp_representation_depth ORDER BY representation_depth_code;"
```

## Positions (issue stances)

File: `data/staging/positions_staging.csv`

Example row (one person’s stance on nullification during 1832–1833):

- person_id: use the `people.person_id` from `unionism.db`
- date_start/date_end: ISO-ish `YYYY-MM-DD`

```
person_id,person_name,event_id,date_start,date_end,issue_category_code,position_label_code,ideology_score,scale_level_code,region_relevance_code,stance_on_union,stance_on_states_rights,stance_on_slavery,stance_on_secession,claim_type_code,confidence_score,evidence_type_code,counterevidence_present,source_id,source_type_code,source_title,source_creator,source_date_created,source_citation_full,source_notes,justification_note,interpretive_note
2,,,1832-11-01,1833-03-01,nullification,constitutional_unionist,,state,,0.8,-0.2,,,observed,2,indirect_reference,0,,letter,"B. F. Perry letters (corpus)","NER extraction pipeline",,,"Auto-generated corpus source; replace with archival citation.","Perry uses pro-Union framing during crisis window.",
```

Notes:
- If you provide `source_id`, you can leave the `source_*` columns blank.
- If you leave `source_id` blank, the loader will look up (or create) a `sources` row using `source_type_code + source_title`.

## Places (locations)

File: `data/staging/places_staging.csv`

Use `lkp_place_type` for `place_type_code` (town/county/state/region/nation/other).

Example rows (a minimal hierarchy):

```
place_id,place_name,place_type_code,parent_place_id,parent_place_name,parent_place_type_code,latitude,longitude,region_sc_code,modern_state,notes
,United States,nation,,,,39.8283,-98.5795,,,Nation (approx center)
,South Carolina,state,,United States,nation,33.8361,-81.1637,,SC,State (approx center)
,Abbeville,town,,South Carolina,state,34.1782,-82.3790,upcountry,SC,
```

Notes:
- Prefer `parent_place_name + parent_place_type_code` when you don’t know IDs.
- `region_sc_code` is optional and should come from `lkp_region_sc`.

Load:

```bash
./.venv/bin/python scripts/load_places_staging.py --dry-run
./.venv/bin/python scripts/load_places_staging.py
```

## Residences (person ↔ place over time)

File: `data/staging/residences_staging.csv`

This is what drives the map position in the MVP UI at year *Y*.

Example row:

```
residence_id,person_id,person_name,place_id,place_name,place_type_code,residence_type_code,date_start,date_end,source_id,source_type_code,source_title,source_creator,source_date_created,source_citation_full,source_notes,notes
,,James L. Petigru,,Charleston,town,professional_base,1830-01-01,,,
```

Notes:
- Provide `person_id` (recommended) or an exact `person_name`.
- Provide `place_id` (recommended) or (`place_name` + `place_type_code`).
- `residence_type_code` should come from `lkp_residence_type`.

Load:

```bash
./.venv/bin/python scripts/load_residences_staging.py --dry-run
./.venv/bin/python scripts/load_residences_staging.py
```

## Events (timeline anchors)

File: `data/staging/events_staging.csv`

Use `lkp_event_type` for `event_type_code` (political_crisis/election/party_realignment/etc.).

Example rows:

```
event_id,event_name,event_type_code,start_date,end_date,place_id,place_name,place_type_code,description
,Nullification Crisis,political_crisis,1832-11-01,1833-03-01,,South Carolina,state,Anchor event window.
,South Carolina Secession Convention,political_crisis,1860-12-17,1860-12-20,,Columbia,town,Convention window.
```

Load:

```bash
./.venv/bin/python scripts/load_events_staging.py --dry-run
./.venv/bin/python scripts/load_events_staging.py
```

## Relationship characterizations (issue-specific fracture/alignment)

File: `data/staging/relationship_characterizations_staging.csv`

Example row (issue-specific alignment for a baseline tie):

```
relationship_id,person_a,person_b,relationship_type_code,baseline_start_date,baseline_end_date,baseline_strength,baseline_alignment_status_code,baseline_source_id,baseline_notes,event_id,date_start,date_end,issue_category_code,scale_level_code,alignment_status_code,strength,claim_type_code,confidence_score,evidence_type_code,counterevidence_present,source_id,source_type_code,source_title,source_creator,source_date_created,source_citation_full,source_notes,justification_note,notes
,2,"Joel R. Poinsett",political_alliance,1830-01-01,,2,,,,,1832-11-01,1833-03-01,nullification,state,aligned,2,observed,2,indirect_reference,0,,letter,"B. F. Perry letters (corpus)","NER extraction pipeline",,,"Auto-generated corpus source; replace with archival citation.",,"Evidence indicates rhetorical alignment during crisis.",
```

Notes:
- If `relationship_id` is blank, the loader will create/find a baseline row in `relationships` for the pair + `relationship_type_code`.
- `person_a`/`person_b` can be a person_id (e.g. `2`) or an exact name (e.g. `Joel R. Poinsett`).
