-- =============================================================================
-- Slice 01 — Nullification Crisis (1830–1833): JAMES LOUIS PETIGRU
-- =============================================================================
-- Purpose: hand-code one actor end-to-end as a template for the rest of the
-- twelve-actor Nullification slice. Every claim is dated and sourced.
--
-- This file is RE-RUNNABLE. It uses INSERT OR IGNORE and NOT EXISTS guards so
-- you can edit a justification, re-run, and not duplicate rows. To "rewrite" a
-- claim, delete the offending row by id first, then re-run.
--
-- Existing IDs assumed (verified against unionism.db on 2026-06-02):
--   person_id 685 = James Louis Petigru
--   person_id 832 = James Hamilton, Jr.
--   person_id   2 = Benjamin Franklin Perry
--   place_id  5/6/8/12/13/14/15 = Charleston/Columbia/Abbeville/Eutaw/Beaufort/Flat Woods/Badwell
--   source_id 6 = Pease & Pease, James Louis Petigru
--   source_id 7 = Grayson, Witness To Sorrow
--
-- BACK UP unionism.db BEFORE RUNNING:
--   cp unionism.db unionism.db.bak_pre_petigru_slice_$(date +%Y%m%d_%H%M%S)
-- THEN:
--   sqlite3 unionism.db < data/slices/01_nullification_1830_1833_petigru.sql
-- =============================================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- -----------------------------------------------------------------------------
-- 1) SOURCES — add the two secondary works this slice will lean on
-- -----------------------------------------------------------------------------
-- Carson's edited collection of Petigru's letters (the primary documentary
-- footprint for direct_quote evidence about Petigru's stance).
INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Life, Letters and Speeches of James Louis Petigru, the Union Man of South Carolina',
       'James Petigru Carson (ed.)',
       '1920',
       'W.H. Lowdermilk & Co., Washington, D.C.',
       'Petigru, James Louis, and James Petigru Carson. Life, Letters and Speeches of James Louis Petigru, the Union Man of South Carolina. Washington, D.C.: W.H. Lowdermilk & Co., 1920.'
WHERE NOT EXISTS (
    SELECT 1 FROM sources
    WHERE title = 'Life, Letters and Speeches of James Louis Petigru, the Union Man of South Carolina'
);

-- Neumann's recent monograph on Nullification rhetoric and Unionist counter-mobilization.
INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Bloody Flag of Anarchy: Unionism in South Carolina during the Nullification Crisis',
       'Brian C. Neumann',
       '2022',
       'LSU Press, Baton Rouge',
       'Neumann, Brian C. Bloody Flag of Anarchy: Unionism in South Carolina during the Nullification Crisis. Baton Rouge: LSU Press, 2022.'
WHERE NOT EXISTS (
    SELECT 1 FROM sources
    WHERE title = 'Bloody Flag of Anarchy: Unionism in South Carolina during the Nullification Crisis'
);

-- -----------------------------------------------------------------------------
-- 2) EVENT — Nullification Crisis container event
-- -----------------------------------------------------------------------------
-- Coded conservatively: opens with the Tariff of 1828 fallout / 1830 SC debates
-- and closes with Jackson's Force Bill / Compromise Tariff in March 1833.
INSERT INTO events (event_name, event_type_code, start_date, end_date, place_id, description)
SELECT 'Nullification Crisis',
       'other',
       '1830-12-01',
       '1833-03-15',
       4, -- South Carolina
       'Constitutional and political confrontation between South Carolina and the federal government over the Tariffs of 1828 and 1832, ending with the Force Bill and Compromise Tariff of 1833.'
WHERE NOT EXISTS (SELECT 1 FROM events WHERE event_name = 'Nullification Crisis');

-- -----------------------------------------------------------------------------
-- 3) PEOPLE — fill in Petigru's biographical fields (he is already row 685)
-- -----------------------------------------------------------------------------
-- Born May 10, 1789 in the Abbeville district (Flat Woods); died March 9, 1863
-- in Charleston. Adult professional identity is lowcountry. Source: Pease (6).
UPDATE people
SET birth_year = COALESCE(birth_year, 1789),
    death_year = COALESCE(death_year, 1863),
    birth_place_id = COALESCE(birth_place_id, 14),  -- Flat Woods, Abbeville District
    death_place_id = COALESCE(death_place_id, 5),   -- Charleston
    gender = COALESCE(gender, 'Male'),  -- project convention: 'Male' | 'Female' | 'Unknown' | NULL
    home_region_sc_code = COALESCE(home_region_sc_code, 'lowcountry'),
    occupation = COALESCE(occupation, 'Lawyer'),
    source_density_code = COALESCE(source_density_code, source_density_code),
    notes = COALESCE(notes,
        'Huguenot descent. Spelling changed from Pettigrew to Petigru after college (1809). Attorney general of SC 1822–1830. Leader of Unionist Party during Nullification Crisis.')
WHERE person_id = 685;

-- -----------------------------------------------------------------------------
-- 4) RESIDENCES — Petigru's geographic trajectory (drives the map at year Y)
-- -----------------------------------------------------------------------------
-- Each residence row is dated; the API picks the most-recent active one for
-- the selected year, so the map marker will move as you slide the year.

-- Birth at Flat Woods, Abbeville District, 1789–1800
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685, 14, 'birth', '1789-05-10', '1800-12-31', 6,
       'Born to William Pettigrew and Louise Gilbert at Flat Woods, Abbeville District. Family lost the Flat Woods land in 1800 and moved to Badwell.'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685 AND place_id = 14 AND residence_type_code = 'birth'
);

-- Badwell (mother's family land in Abbeville), 1800–1804, before Waddel's academy
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685, 15, 'household', '1800-01-01', '1804-10-13', 6,
       'After loss of Flat Woods, lived at uncle Joseph Gilbert''s plantation Badwell in Abbeville District until entering Moses Waddel''s academy at Willington in October 1804.'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685 AND place_id = 15 AND residence_type_code = 'household'
);

-- Eutaw / Coosawhatchie / Beaufort lowcountry years, 1809–1819 (teaching + early law)
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685, 13, 'professional_base', '1812-01-01', '1819-12-31', 6,
       'Read law in Beaufort under William Robertson; passed bar 1812; practiced in Coosawhatchie/Beaufort District until partnership with James Hamilton, Jr. drew him to Charleston in 1819.'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685 AND place_id = 13 AND residence_type_code = 'professional_base'
);

-- Charleston, 1819–1863 — the residence that drives the map for the whole slice.
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685, 5, 'professional_base', '1819-01-01', '1863-03-09', 6,
       'Joined James Hamilton, Jr.''s Charleston law firm in 1819; remained in Charleston the rest of his life. Attorney general of SC 1822–1830; leader of Charleston Unionist Party during Nullification Crisis.'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685 AND place_id = 5 AND residence_type_code = 'professional_base'
);

-- -----------------------------------------------------------------------------
-- 5) POSITIONS — Petigru's stances 1830–1833 (NEW STANCE-REDESIGN SCHEMA)
-- -----------------------------------------------------------------------------
-- After the Phase 1 stance redesign (2026-06-03) we no longer code the four
-- stance_on_* scalars as evidentiary claims. The going-forward shape is:
--    stance_code    — categorical against the row's issue_category
--                     ('supports' | 'opposes' | 'qualified' | 'unknown')
--    position_notes — merged justification + interpretation, single defended
--                     prose block
--    position_sources (junction) — many-to-many source attribution with role
--                                  'primary' or 'secondary'
--
-- DUAL-WRITE NOTE: schema.sql still carries the legacy NOT NULL columns
-- (claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
-- source_id, justification_note) until the Phase 3 drop. We fill them with
-- carried-forward values so the INSERT succeeds; the AUTHORITATIVE record is
-- stance_code + position_notes + position_sources. Phase 3 will drop the
-- legacy columns; nothing in this slice will need to be re-coded.
--
-- Three claims, each a separate dated row so the year slider can show drift.

-- 1830: Tariff fallout / opening of the Nullification debate. Petigru opposes
-- nullification doctrine but is still operating inside SC's legal system as
-- attorney general. "Constitutional Unionist" rather than "Absolute Unionist".
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    -- new schema (authoritative)
    stance_code, position_notes,
    -- legacy NOT NULL (carried forward; will be dropped in Phase 3)
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 685,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1832-06-30',
       'nullification', 'constitutional_unionist',
       'state', 'lowcountry',
       'opposes',
       'Petigru opposed nullification on constitutional grounds while still serving as SC attorney general (1822–1830). His correspondence with Hugh S. Legaré and Daniel Huger argued that political change must come through "appropriate and legal channels" — not through state interposition against federal law. Coded as Constitutional Unionist (not Absolute) for this window because Petigru still hopes Calhoun will reverse course; sardonic but not yet despairing.',
       'observed', 3, 'direct_quote', 0,
       6,
       'See position_notes (Phase 1 dual-write, 2026-06-03).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'nullification' AND date_start = '1830-01-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, James Louis Petigru — biographical narrative of Petigru''s 1830 Unionist correspondence and AG-era opposition to nullification.'
  FROM positions pos
 WHERE pos.person_id = 685
   AND pos.issue_category_code = 'nullification'
   AND pos.date_start = '1830-01-01';

-- 1832: Test Oath / SC Convention. The radical turn forces Petigru to a harder
-- line. He becomes a leader of the Charleston Unionist counter-mobilization.
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 685,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1832-07-01', '1833-03-15',
       'nullification', 'absolute_unionist',
       'state', 'lowcountry',
       'opposes',
       'After the "overwhelming success of the Nullification ticket" in the October 1832 elections and the convention''s call for the Test Oath, Petigru rejects compromise. His December 1832 letter to Legaré (chargé d''affaires in Brussels) describing the "curious" scene in SC and the embarrassment of Johnson, O''Neall, and Manning over the test oath documents this hardening. Same categorical stance (opposes nullification) as the 1830 row but escalated to Absolute Unionist on the position_label axis — pair this with the corresponding relationship_characterization row marking the fracture with Hamilton, Jr.',
       'observed', 3, 'direct_quote', 0,
       6,
       'See position_notes (Phase 1 dual-write, 2026-06-03).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'nullification' AND date_start = '1832-07-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, James Louis Petigru, ch. 4 — narrative of the Test Oath aftermath and Petigru''s December 1832 Legaré letter.'
  FROM positions pos
 WHERE pos.person_id = 685
   AND pos.issue_category_code = 'nullification'
   AND pos.date_start = '1832-07-01';

-- 1832: parallel claim on federal_power (national scale) — Petigru's defense
-- of federal supremacy over state interposition. Same source, separate issue,
-- so it can light up the network when "federal_power" is the selected issue.
-- Stance flips polarity here because the issue is federal_power, not nullification:
-- Petigru SUPPORTS federal supremacy / OPPOSES nullification (same Unionism, two issue axes).
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 685,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1832-07-01', '1833-03-15',
       'federal_power', 'constitutional_unionist',
       'national', NULL,
       'supports',
       'Petigru''s public writings during the convention period defended federal supremacy and the constitutionality of the tariff power; he opposed nullification as an extralegal interposition that would unmake the federal compact. Coding the federal_power axis separately from the nullification axis lets the visualization isolate "defenders of national authority" from "opponents of state interposition" — overlapping but distinct constituencies in 1832–1833.',
       'observed', 3, 'direct_quote', 0,
       6,
       'See position_notes (Phase 1 dual-write, 2026-06-03).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'federal_power' AND date_start = '1832-07-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, James Louis Petigru — Petigru''s public defenses of federal supremacy during the convention period.'
  FROM positions pos
 WHERE pos.person_id = 685
   AND pos.issue_category_code = 'federal_power'
   AND pos.date_start = '1832-07-01';

-- -----------------------------------------------------------------------------
-- 6) BASELINE RELATIONSHIPS — the ties that will be characterized over issues
-- -----------------------------------------------------------------------------
-- Note: the relationships table requires person_low_id < person_high_id.
-- Petigru = 685, Hamilton = 832, Perry = 2. So pairs are (685,832) and (2,685).

-- Petigru ↔ Hamilton, Jr.: legal partnership 1819–1822, then political alliance
-- (Hamilton hands the Charleston firm to Petigru in 1822 when he leaves for
-- Congress). This is the baseline relationship that will *fracture* over
-- nullification once Hamilton becomes a leading Nullifier.
INSERT OR IGNORE INTO relationships (
    person_low_id, person_high_id, relationship_type_code,
    start_date, end_date, strength, alignment_status_code, source_id, notes
) VALUES (
    685, 832, 'legal_connection',
    '1819-01-01', '1822-12-31', 3, 'aligned', 6,
    'Petigru joined Hamilton''s Charleston law firm as junior partner in 1819 and assumed senior leadership when Hamilton left for Congress in 1822.'
);

INSERT OR IGNORE INTO relationships (
    person_low_id, person_high_id, relationship_type_code,
    start_date, end_date, strength, alignment_status_code, source_id, notes
) VALUES (
    685, 832, 'political_alliance',
    '1819-01-01', '1857-11-15', 2, 'partially_aligned', 6,
    'Through the 1820s Petigru and Hamilton operated as Charleston legal-political peers; the alliance frayed as Hamilton moved toward Nullifier leadership in 1830 and remained fractured through Hamilton''s death in 1857. End_date marks Hamilton''s death (steamboat Opelousas), not the alignment flip — the issue-specific fracture is captured by the relationship_characterizations row.'
);

-- Petigru ↔ Perry: political alliance as the two most prominent SC Unionists
-- across the lowcountry/upcountry axis. Perry = 2, Petigru = 685, so low<high.
INSERT OR IGNORE INTO relationships (
    person_low_id, person_high_id, relationship_type_code,
    start_date, end_date, strength, alignment_status_code, source_id, notes
) VALUES (
    2, 685, 'political_alliance',
    '1830-01-01', '1860-12-31', 3, 'aligned', 6,
    'Petigru (Charleston, lowcountry) and Perry (Greenville, upcountry) functioned as the two anchoring elite Unionists from Nullification through the 1860 Charleston convention; correspondence and mutual public defense run through this period.'
);

-- -----------------------------------------------------------------------------
-- 7) RELATIONSHIP CHARACTERIZATIONS — issue-specific, dated alignment shifts
-- -----------------------------------------------------------------------------
-- This is where "coalescence and fracture" become visible. The renderer at /
-- will color the edge using the active characterization at the selected year.
--
-- New schema (Phase 1, 2026-06-03):
--   stance_code     — categorical (NULL on relchar in this slice; alignment_status_code
--                     remains the primary edge-color driver, per the locked design)
--   relchar_notes   — merged justification + interpretation
--   relchar_sources — many-to-many source attribution
-- Legacy NOT NULL columns (claim_type_code, confidence_score, evidence_type_code,
-- counterevidence_present, source_id, justification_note) carried forward until Phase 3.

-- FRACTURE: Petigru ↔ Hamilton over nullification, 1830–1833.
INSERT OR IGNORE INTO relationship_characterizations (
    relationship_id, event_id, date_start, date_end,
    issue_category_code, scale_level_code, alignment_status_code, strength,
    relchar_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT
    (SELECT relationship_id FROM relationships
      WHERE person_low_id = 685 AND person_high_id = 832
        AND relationship_type_code = 'political_alliance'),
    (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
    '1830-07-01', '1833-03-15',
    'nullification', 'state', 'fractured', 3,
    'Hamilton''s emergence as a leading Nullifier (governor 1830–1832, central architect of the SC Convention) places him in direct, public opposition to Petigru''s Unionist mobilization in Charleston. The fracture is on nullification specifically; their prior legal-professional cooperation does not survive intact.',
    'observed', 3, 'mixed', 0,
    6,
    'See relchar_notes (Phase 1 dual-write, 2026-06-03).';

INSERT OR IGNORE INTO relchar_sources (relationship_characterization_id, source_id, source_role, notes)
SELECT rc.relationship_characterization_id, 6, 'primary', 'Pease & Pease, James Louis Petigru, ch. 4.'
  FROM relationship_characterizations rc
  JOIN relationships r ON r.relationship_id = rc.relationship_id
 WHERE r.person_low_id = 685 AND r.person_high_id = 832
   AND rc.issue_category_code = 'nullification'
   AND rc.date_start = '1830-07-01';

-- ALIGNMENT: Petigru ↔ Perry on nullification, 1830–1833. The lowcountry/
-- upcountry Unionist axis that anticipates the 1860 convention scene.
INSERT OR IGNORE INTO relationship_characterizations (
    relationship_id, event_id, date_start, date_end,
    issue_category_code, scale_level_code, alignment_status_code, strength,
    relchar_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT
    (SELECT relationship_id FROM relationships
      WHERE person_low_id = 2 AND person_high_id = 685
        AND relationship_type_code = 'political_alliance'),
    (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
    '1830-01-01', '1833-03-15',
    'nullification', 'state', 'aligned', 3,
    'Petigru and Perry operate as coordinated Unionist voices across the lowcountry/upcountry divide during the Nullification Crisis. Their correspondence after the 1860 Charleston Democratic Convention (Petigru to Perry on his "disinclination to write or to speak when truth is in question") confirms a long-standing shared stance traceable back to the 1830s.',
    'observed', 3, 'mixed', 0,
    6,
    'See relchar_notes (Phase 1 dual-write, 2026-06-03).';

INSERT OR IGNORE INTO relchar_sources (relationship_characterization_id, source_id, source_role, notes)
SELECT rc.relationship_characterization_id, 6, 'primary', 'Pease & Pease, James Louis Petigru — narrative of long-running Petigru–Perry Unionist coordination.'
  FROM relationship_characterizations rc
  JOIN relationships r ON r.relationship_id = rc.relationship_id
 WHERE r.person_low_id = 2 AND r.person_high_id = 685
   AND rc.issue_category_code = 'nullification'
   AND rc.date_start = '1830-01-01';

-- =============================================================================
COMMIT;

-- -----------------------------------------------------------------------------
-- VERIFICATION QUERIES — run these manually after the script:
-- -----------------------------------------------------------------------------
-- .headers on
-- .mode column
-- SELECT position_id, issue_category_code, date_start, date_end,
--        position_label_code, stance_code, substr(position_notes,1,80) AS notes_preview
--   FROM positions WHERE person_id = 685 ORDER BY date_start;
-- SELECT ps.position_id, ps.source_id, ps.source_role, s.title
--   FROM position_sources ps JOIN sources s ON s.source_id = ps.source_id
--   JOIN positions p ON p.position_id = ps.position_id
--  WHERE p.person_id = 685;
-- SELECT * FROM person_place_residence WHERE person_id = 685 ORDER BY date_start;
-- SELECT rc.relationship_characterization_id, r.person_low_id, r.person_high_id,
--        rc.issue_category_code, rc.date_start, rc.alignment_status_code,
--        rc.stance_code, substr(rc.relchar_notes,1,80) AS notes_preview
--   FROM relationship_characterizations rc
--   JOIN relationships r ON r.relationship_id = rc.relationship_id
--  WHERE r.person_low_id = 685 OR r.person_high_id = 685;
-- =============================================================================
