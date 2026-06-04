# Work Log — UnionismNetwork

## Project intent (1–3 sentences)
- Goal: Create a temporal social network that is geographically grounded. The network will show coalescence and fracture between prominant South Carolina Unionists over socio-political issues from 1828-1860.

- Data sources involved (folders/repos): Benjamin Franklin Perry Letters; James Louis Petigru Letters and Speeches; various secondary sources

- Current “pipeline” summary: The Perry and Petigru letters were split and loaded from their digitized/transcribed sources. NER was run to identify person and location entities. People were loaded into respective CSVs and manaully reviewed. People were then loaded into the UnionismNetwork db.

## Conventions / rules I’m using
- people_review actions:
  - keep = First and Last Names
  - merge = First and Last Name combinations that are clearly the same person (often an incorrect character, plural, or plural)
  - drop = Words that are clearly not names, characters, multiple names joined by '&', categories of people (editors, governors, grandchildren, etc.)
  - review = First or Last Name only
- Merge key: canonical_key and person id
- Only keep/merge load into DB: yes/no

---
## 2026-05-03
### What I changed
- Combined UnionismNetwork, PerryLetters and Petigru folders into a single workspace

### Why / decision notes
- I was having difficulty with Copilot due to toggling back and forth between UnionismNetwork and PerryLetters. I needed to get the people the db in PerryLetters into UnionismNetwork.

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced: people_review.csv, unionism_aliases_staging.csv, unionism_people_staging.csv; I copied people_review.csv and created people_review_edited.csv per Copilot's suggestion to preserve the original file

### Checks / results
- Row counts:
- Any errors:

### Next
- Manual correction of people_review.csv

## 2026-06-01
### What I changed
- Restructured Petigru NER results into staging csv

### Why / decision notes
- Matched review process utitlized with Perry NER results; Petigru entities had a lot of junk compared to Perry in network

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced: petigru_ner_review.csv

### Checks / results
- Row counts:
- Any errors:

### Next
- Reevaluate current state of project and determine next steps

## YYYY-MM-DD
### What I changed
- 

### Why / decision notes
- 

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced:

### Checks / results
- Row counts:
- Any errors:

### Next
- 

## YYYY-MM-DD
### What I changed
- 

### Why / decision notes
- 

### Commands I ran (copy/paste)
- 

### Inputs
- Source files used:
- Output files produced:

### Checks / results
- Row counts:
- Any errors:

### Next
- 
---

## 2026-06-03 — Phase 1: Stance redesign (additive only)

### Goal
Replace the four scalar stance_on_* floats and the confidence/claim/evidence apparatus on `positions` and `relationship_characterizations` with a single categorical `stance_code` defended in `notes`. Phase 1 is **additive only** — nothing dropped, nothing renamed; new columns/tables coexist with legacy. See `/memories/repo/UnionismNetwork-conventions.md` for the full redesign spec.

### Inputs
- `schema.sql` — added `lkp_stance` table, `stance_code`/notes columns on `positions` and `relationship_characterizations`, `position_sources` and `relchar_sources` junction tables, supporting indexes, and `INSERT OR IGNORE` seed for `lkp_stance` (4 rows).
- `scripts/apply_schema.py` — rewritten to introspect existing column lists and run `ALTER TABLE ADD COLUMN` for missing additive columns *before* executing schema.sql (so new indexes can resolve their columns on existing DBs).

### Pre-change backup
- `unionism.db.bak_pre_stance_redesign_phase1_20260603_065524`

### Checks / results
- `lkp_stance` rows: 4 (`supports`, `opposes`, `qualified`, `unknown`)
- `positions.stance_code` (NULL), `positions.position_notes` (NULL) — added
- `relationship_characterizations.stance_code` (NULL), `relationship_characterizations.relchar_notes` (NULL) — added
- `position_sources`, `relchar_sources` tables created
- Existing data preserved: people=1163, relationships=2033, positions=1, relchar=3
- All legacy columns untouched; existing API and UI continue to read them unchanged.

### Notes / pitfalls
- Initial run failed because `executescript(schema.sql)` ran before the additive ALTERs; the new `idx_positions_stance` index referenced a column that didn't yet exist on the existing table. Fix: ALTER first, then executescript.
- A separate self-inflicted syntax error briefly dropped the `UNIQUE (...)` clause on `relationship_characterizations` during editing. Caught immediately; restored.

### Next phases (not yet started)
- Phase 2: backfill the existing 1 position + 3 characterization rows into the new columns; cut `/api/state` over to read `stance_code` for node coloring; update `/api/people/{id}` and people page.
- Phase 3: drop the legacy stance_on_* floats, `ideology_score`, `claim_type_code`, `confidence_score`, `evidence_type_code`, `counterevidence_present`, single `source_id` FKs, `strength` on relationships and relchar, `justification_note`, `interpretive_note`, and the `lkp_claim_type`/`lkp_evidence_type`/`lkp_confidence_score` lookup tables. SQLite ALTER-by-rebuild migration.

---

## 2026-06-04 — Petigru hand-coded slice (Nullification 1830–1833)

### Goal
Hand-code James Louis Petigru end-to-end as the template for the twelve-actor Nullification slice: bio, residences, three dated positions (nullification 1830, nullification 1832 escalation to Absolute Unionist, federal_power 1832), three baseline relationships (Petigru–Hamilton legal_connection, Petigru–Hamilton political_alliance, Petigru–Perry political_alliance), and two issue-dated relationship_characterizations (Hamilton fracture + Perry alignment).

### Inputs
- `data/slices/01_nullification_1830_1833_petigru.sql` (re-runnable, INSERT OR IGNORE / NOT EXISTS guards)
- Sources added: 6 = Pease & Pease, *James Louis Petigru*; 7 = Grayson, *Witness To Sorrow*; Carson 1920 letters; Neumann 2022 *Bloody Flag of Anarchy*

### Pre-change backup
- `unionism.db.bak_pre_petigru_slice_20260604_064024`

### Checks / results
- positions(685): 3 rows (nullification 1830-01-01 / 1832-07-01; federal_power 1832-07-01)
- person_place_residence(685): 4 rows (Flat Woods, Badwell, Beaufort, Charleston)
- relationships: (685,832) legal_connection + political_alliance, (2,685) political_alliance
- relationship_characterizations: 2 rows (Hamilton fractured 1830-07-01, Perry aligned 1830-01-01)
- Validated at /?year=1832&issue=nullification: red node at Charleston, fractured edge to Hamilton, aligned edge to Perry

---

## 2026-06-04 — Petigru–Hamilton temporal modeling fix

### Goal
Fix invisible Hamilton fracture at year 1832: `relationships.end_date` had been set to 1830-06-30 (alignment flip), so the underlying tie no longer existed in 1832 and the relchar fracture row had no edge to color.

### Change
- Slice file: extended `(685,832,'political_alliance')` end_date from 1830-06-30 to 1857-11-15 (Hamilton's death aboard SS *Opelousas*); added explanatory note that the issue-specific fracture lives in `relationship_characterizations`, never on the parent relationship.
- Locked modeling rule into `/memories/repo/UnionismNetwork-conventions.md`: `relationships.end_date` marks when the relationship ends absolutely (typically death). Issue-specific alignment changes go ONLY in `relationship_characterizations`.

### Pre-change backup
- `unionism.db.bak_pre_pethamilton_fix_20260604_065311`

---

## 2026-06-04 — Phase 2: API + frontend cutover to stance_code

### Goal
Cut `/api/state`, `/api/people/{id}`, `/api/lookups`, and the D3 renderer over to the new `stance_code` + `position_notes` + `position_sources` schema. Legacy stance_on_* floats no longer feed the visualization.

### Inputs
- `app/main.py`: `/api/state` nodes_sql now selects `stance_code`, `position_notes`, and a derived `stance_source_id` (from `position_sources` WHERE source_role='primary' for the active position). `/api/people/{id}` positions query now packs sources via `GROUP_CONCAT(source_id || ':' || source_role, '|')`. `/api/lookups` adds `("stance","lkp_stance","stance_code")`.
- `app/static/app.js`: added `stanceColor()` (supports=#46d369, opposes=#ff6b6b, qualified=#f2c14e, unknown=#9aa0aa). `isPersonCoded()` now keys on `stance_code || position_label_code`. Selection moved off fill onto stroke (blue ring) so stance color stays visible. Details panel renders a `.stancePill` + position_notes + primary source citation block.
- `app/static/styles.css`: `.stancePill` base + `.stance-supports/opposes/qualified/unknown` color variants.

### Pre-change backup
- `unionism.db.bak_pre_phase2_20260604_070001`

### Checks / results
- Petigru @ 1832 issue=nullification → red, opposes
- Petigru @ 1832 issue=federal_power → green, supports
- Petigru @ 1834+ → light gray (no stance row for those years)
- Selection ring no longer overrides stance fill

### Next phases
- Phase 3: drop the legacy stance_on_*/ideology_score/claim_type_code/confidence_score/evidence_type_code/counterevidence_present/source_id/justification_note/interpretive_note columns from positions & relchar; drop `strength` from relationships and relchar; SQLite ALTER-by-rebuild.
- Backfill stance_code on the few pre-existing legacy rows.

---

## 2026-06-04 — Cleanup pass: Petigru NER co_mentions + bad residence

### Goal
Remove NER pollution that was crowding the Petigru ego-network and conflicting with the hand-coded slice rows.

### Change
- Deleted 20 `co_mentioned` relationship rows incident to Petigru (source 5, NER aggregate).
- Deleted residence_id 22 (legacy malformed Petigru residence row).

### Pre-change backup
- `unionism.db.bak_pre_cleanup_20260604_071149`

---

## 2026-06-04 — Relationship type code normalization

### Goal
Resolve Perry-vs-Petigru network asymmetry: three distinct NER-derived relationship_type_codes (`co_mentioned`, `corpus_mention`, `corpus_co_mention`) were being written by two different NER ingestion scripts at different times. The frontend "Hide co-mentions" toggle filtered only the literal string `co_mentioned`, so Petigru's NER edges were hidden but Perry's 530 `corpus_mention` + 957 `corpus_co_mention` rows passed through as if they were curated history.

### Change
- Deleted 3 collision rows that shared (person_low_id, person_high_id, start_date) with a sibling: relationship_ids 1055, 1056, 1247 (all `corpus_co_mention`, all anchored at Perry / 1817-01-01). No relchar references existed.
- `UPDATE relationships SET relationship_type_code='co_mentioned'` where the code was `corpus_mention` or `corpus_co_mention` → 1,484 rows updated.
- Deleted the two now-orphan rows from `lkp_relationship_type` (`corpus_mention`, `corpus_co_mention`).
- Flipped ingest script defaults to canonical:
  - `scripts/link_corpus_mentions.py` → `co_mentioned` / "Co-mentioned in correspondence"
  - `scripts/link_co_mentions_from_perryletters.py` → `co_mentioned` / "Co-mentioned in correspondence"

### Pre-change backup
- `unionism.db.bak_pre_reltype_normalize_20260604_073042`

### Checks / results
- relationships by type after normalize:
  - co_mentioned: 1998
  - kinship: 4, political_alliance: 4, friendship: 2, legal_connection: 2, kinship_extended/parent_child/spouse: 1 each
- Existing JS toggle (`isCoMentionEdge` matches `'co_mentioned'`) and `app.js` line-93 within-layer filter now correctly hide all NER-derived edges for both corpora.


## 2026-06-04 — Petigru residence cleanup (finished)

### Change
- Deleted residence_ids 8, 13, 15, 16, 20 — all auto-generated "via membership in organization N" stubs (Columbia 1806–1809 was wrong: Petigru was at Waddel's academy in Willington; Eutaw 1809–1810 had no notes; Beaufort 1810–1812 was redundant with the slice's Beaufort professional_base 1812–1819 row).
- Updated residence_id 24 (Badwell, real, has Joseph Gilbert notes) to ISO dates `1800-01-01` / `1804-10-13` for consistency with slice convention.

### Pre-change backup
- `unionism.db.bak_pre_petigru_residence_cleanup_20260604_073...` (in workspace)

### Final state
- Petigru residences (4 rows): Flat Woods (birth 1789–1800) → Badwell (household 1800–1804) → Beaufort (professional_base 1812–1819) → Charleston (professional_base 1819–1863).

---

## 2026-06-04 — Hamilton Jr. slice (Nullification 1830–1833)

### Goal
Hand-code James Hamilton, Jr. (person_id 832) as the canonical Nullifier counter-pole to Petigru, so the visualization carries both sides of the 1830–1833 fracture: bio + Charleston residence trajectory + four dated positions + three new baseline relationships + three relchars.

### Inputs
- `data/slices/02_nullification_1830_1833_hamilton.sql` (re-runnable)
- Sources: source 9 = Neumann, *Bloody Flag of Anarchy* (primary); source 6 = Pease & Pease (secondary corroboration)

### Vocabulary additions
- `lkp_position_label`: added `nullifier` and `radical_nullifier` (project's label vocabulary had been Unionist-only; Hamilton, Calhoun, McDuffie, Hayne, Turnbull, Cooper need this).

### Pre-change backup
- `unionism.db.bak_pre_hamilton_slice_20260604_07...`

### Checks / results
- Hamilton positions (4 rows):
  - nullification 1828-12-01 → 1830-06-30 — `nullifier` / supports (Tariff of Abominations / Exposition era)
  - nullification 1830-12-09 → 1832-12-09 — `radical_nullifier` / supports (governorship)
  - nullification 1832-11-19 → 1833-03-15 — `radical_nullifier` / supports (Convention President / Test Oath)
  - federal_power 1830-12-09 → 1833-03-15 — `radical_nullifier` / opposes (mirror of Petigru's "supports federal_power")
- Hamilton residences (2 rows): Charleston birth 1786–1800; Charleston professional_base 1810–1857 (death aboard SS *Opelousas*)
- New relationships: (272,832) Calhoun-Hamilton political_alliance 1820–1850; (176,832) McDuffie-Hamilton political_alliance 1825–1851; (2,832) Perry-Hamilton political_alliance 1828–1857 (alignment=fractured)
- New relchars (3): Calhoun-Hamilton aligned on nullification, McDuffie-Hamilton aligned on nullification, Perry-Hamilton fractured on nullification 1830–1833. Existing rc 4 (Petigru-Hamilton fracture) unchanged.

### Next
- Hayne, Calhoun, McDuffie position rows (their relchars to Hamilton already exist; positions are still missing).
- Phase 3 column drops.
