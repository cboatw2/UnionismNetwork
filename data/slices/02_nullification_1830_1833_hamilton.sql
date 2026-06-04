-- =============================================================================
-- Slice 02 — Nullification Crisis (1830–1833): JAMES HAMILTON, JR.
-- =============================================================================
-- Purpose: hand-code the canonical Nullifier counter-pole to the Petigru slice.
-- Hamilton is the architect of the SC Convention and its Test Oath, governor
-- 1830–1832, and President of the Convention in November 1832. Coding him
-- end-to-end gives the visualization a proper "fracture across the room" so
-- Petigru's red Unionist node can connect to Hamilton's green Nullifier node
-- via the existing relchar fracture row.
--
-- This file is RE-RUNNABLE. INSERT OR IGNORE / NOT EXISTS guards throughout.
--
-- Existing IDs assumed (verified against unionism.db on 2026-06-04):
--   person_id 832 = James Hamilton, Jr.
--   person_id 685 = James Louis Petigru
--   person_id   2 = Benjamin Franklin Perry
--   person_id 272 = John C. Calhoun
--   person_id 176 = George McDuffie
--   place_id    5 = Charleston
--   source_id   6 = Pease & Pease, James Louis Petigru
--   source_id   9 = Neumann, Bloody Flag of Anarchy (LSU 2022)
--
-- BACK UP unionism.db BEFORE RUNNING:
--   cp unionism.db unionism.db.bak_pre_hamilton_slice_$(date +%Y%m%d_%H%M%S)
-- THEN:
--   sqlite3 unionism.db < data/slices/02_nullification_1830_1833_hamilton.sql
-- =============================================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- -----------------------------------------------------------------------------
-- 0) VOCABULARY — add Nullifier position labels (project was Unionist-only)
-- -----------------------------------------------------------------------------
-- These are needed for Hamilton, Calhoun, McDuffie, Hayne, Turnbull, Cooper, etc.
-- so the network can carry both poles of the 1830–1833 confrontation.
INSERT OR IGNORE INTO lkp_position_label (position_label_code, label) VALUES
    ('nullifier',         'Nullifier'),
    ('radical_nullifier', 'Radical Nullifier');

-- -----------------------------------------------------------------------------
-- 1) PEOPLE — fill in Hamilton's biographical fields
-- -----------------------------------------------------------------------------
-- Born May 8, 1786 in Charleston. Drowned Nov 15, 1857 in the Gulf of Mexico
-- when steamboat Opelousas collided with the Galveston; gave his life-preserver
-- to a woman with a child. Lawyer; mayor of Charleston during the Vesey trial
-- (1822); US Representative 1822–1829; governor of SC 1830–1832; President of
-- the SC Nullification Convention November 1832.
UPDATE people
SET birth_year         = COALESCE(birth_year, 1786),
    death_year         = COALESCE(death_year, 1857),
    birth_place_id     = COALESCE(birth_place_id, 5),  -- Charleston
    death_place_id     = COALESCE(death_place_id, NULL),  -- at sea, Gulf of Mexico
    gender             = COALESCE(gender, 'Male'),
    home_region_sc_code= COALESCE(home_region_sc_code, 'lowcountry'),
    occupation         = COALESCE(occupation, 'Lawyer / Politician / Planter'),
    notes              = COALESCE(NULLIF(notes,''),
        'Charleston Federalist-turned-Jeffersonian; mayor of Charleston during the Denmark Vesey trial (1822); US Representative 1822–1829; Governor of SC 1830–1832; President of the SC Nullification Convention, November 1832 — the architect of the Test Oath. Petigru''s former law partner (1819–1822). After Nullification, accumulated debt as a Texas land speculator. Drowned Nov 15, 1857 when the steamboat Opelousas collided with the Galveston in the Gulf of Mexico, giving his life-preserver to a fellow passenger.')
WHERE person_id = 832;

-- -----------------------------------------------------------------------------
-- 2) RESIDENCES — clean and dated
-- -----------------------------------------------------------------------------
-- Drop the pre-existing legacy stub (residence_id 28: Charleston household with
-- no dates and no source) so the slice's clean dated rows can stand alone.
DELETE FROM person_place_residence
 WHERE person_id = 832
   AND place_id = 5
   AND residence_type_code = 'household'
   AND date_start IS NULL
   AND date_end   IS NULL;

-- Birth in Charleston, 1786–1800 (childhood through schooling)
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 832, 5, 'birth', '1786-05-08', '1800-12-31', 6,
       'Born in Charleston to James Hamilton, Sr. (Revolutionary War officer) and Elizabeth Lynch.'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 832 AND place_id = 5 AND residence_type_code = 'birth'
);

-- Charleston professional / political base, 1810–1857
-- Hamilton's Charleston tie is continuous from his return to law practice
-- through the rest of his life; even during his Texas land-speculation years
-- (mid-1830s onward) Charleston remained his SC anchor. End_date = death.
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 832, 5, 'professional_base', '1810-01-01', '1857-11-15', 9,
       'Returned to Charleston after early military service in the War of 1812; built law practice with Petigru as junior partner from 1819 to 1822; served as mayor (intendant) during the Denmark Vesey trial in 1822; left for the US House later that year. Resumed Charleston as political base 1829–1832 as governor and Convention president. Continued to anchor SC affairs from Charleston even as Texas land deals consumed his finances after 1834.'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 832 AND place_id = 5 AND residence_type_code = 'professional_base'
);

-- -----------------------------------------------------------------------------
-- 3) POSITIONS — Hamilton's stances 1828–1833
-- -----------------------------------------------------------------------------
-- Three dated rows so the year slider can show his radicalization.

-- 1828–1830: opening of the Nullification debate. Hamilton has helped author
-- the South Carolina Exposition and Protest behind the scenes (Calhoun's hand
-- but Hamilton's coordination). He supports the doctrine in principle but is
-- not yet calling for a state convention.
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 832,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1828-12-01', '1830-06-30',
       'nullification', 'nullifier',
       'state', 'lowcountry',
       'supports',
       'After the Tariff of 1828 ("Tariff of Abominations") Hamilton emerged as the public face of the Nullification cause in Charleston, coordinating with Calhoun on the South Carolina Exposition and Protest. In this opening window he advocates state interposition as the legitimate constitutional remedy but has not yet pushed for a convention; the strategy is still legislative protest plus organized public opinion.',
       'observed', 3, 'mixed', 0,
       9,
       'See position_notes (Phase 1 dual-write, 2026-06-04).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 832 AND issue_category_code = 'nullification' AND date_start = '1828-12-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — Hamilton''s Charleston coordination with Calhoun on the Exposition and Protest.'
  FROM positions pos
 WHERE pos.person_id = 832
   AND pos.issue_category_code = 'nullification'
   AND pos.date_start = '1828-12-01';

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'secondary', 'Pease & Pease, James Louis Petigru — corroborating narrative of Hamilton''s 1828–1830 Nullification mobilization in Charleston.'
  FROM positions pos
 WHERE pos.person_id = 832
   AND pos.issue_category_code = 'nullification'
   AND pos.date_start = '1828-12-01';

-- 1830–1832: governor of SC. The radicalization. Hamilton uses the governorship
-- to organize the Nullifier party machinery, ride the upcountry/lowcountry
-- coalition, and force the legislature toward the convention call.
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 832,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-12-09', '1832-12-09',
       'nullification', 'radical_nullifier',
       'state', 'lowcountry',
       'supports',
       'As governor of South Carolina (Dec 1830–Dec 1832) Hamilton converts the Nullifier program from doctrine into machinery: state-wide associations, militia preparation, electoral mobilization for the October 1832 ticket. By the end of his term he has secured the convention call that Petigru and the Charleston Unionists organized to defeat. Coded as Radical Nullifier (not just Nullifier) because his governorship marks the move from constitutional argument to coercive mobilization, including the embryonic Test Oath that he will preside over in November.',
       'observed', 3, 'mixed', 0,
       9,
       'See position_notes (Phase 1 dual-write, 2026-06-04).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 832 AND issue_category_code = 'nullification' AND date_start = '1830-12-09'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — Hamilton''s gubernatorial Nullifier mobilization 1830–1832.'
  FROM positions pos
 WHERE pos.person_id = 832
   AND pos.issue_category_code = 'nullification'
   AND pos.date_start = '1830-12-09';

-- 1832 Nov–1833 Mar: President of the Nullification Convention. The Test Oath.
-- This is the apex of the Nullifier project and the moment that hardens the
-- Petigru–Hamilton fracture from political opposition into open factional war.
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 832,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1832-11-19', '1833-03-15',
       'nullification', 'radical_nullifier',
       'state', 'lowcountry',
       'supports',
       'Elected President of the South Carolina Nullification Convention (Nov 19, 1832), Hamilton presides over the Ordinance of Nullification and the Test Oath that obliged state officeholders to repudiate federal authority. The Test Oath crystallizes the Charleston Unionist counter-mobilization that Petigru leads — the same December 1832 moment Petigru describes to Legaré. Hamilton''s position holds through the Compromise Tariff/Force Bill resolution in March 1833.',
       'observed', 3, 'mixed', 0,
       9,
       'See position_notes (Phase 1 dual-write, 2026-06-04).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 832 AND issue_category_code = 'nullification' AND date_start = '1832-11-19'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — Convention proceedings and the Test Oath, Nov 1832–Mar 1833.'
  FROM positions pos
 WHERE pos.person_id = 832
   AND pos.issue_category_code = 'nullification'
   AND pos.date_start = '1832-11-19';

-- 1832: parallel federal_power claim — Hamilton OPPOSES federal supremacy
-- (mirror of Petigru's "supports federal_power" row). This lets the federal_power
-- issue lens at year=1832 show the same fracture from the opposite stance pole.
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 832,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-12-09', '1833-03-15',
       'federal_power', 'radical_nullifier',
       'national', NULL,
       'opposes',
       'Hamilton''s Nullifier project is, by definition, an argument against unilateral federal supremacy on the tariff power. The federal_power axis lets the network show that opponents of nullification (Petigru) and opponents of federal supremacy (Hamilton) line up on the same fault but from opposite sides — the structural symmetry that makes 1832 a fracture rather than a debate.',
       'observed', 3, 'mixed', 0,
       9,
       'See position_notes (Phase 1 dual-write, 2026-06-04).'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 832 AND issue_category_code = 'federal_power' AND date_start = '1830-12-09'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — Nullifier doctrine on federal supremacy.'
  FROM positions pos
 WHERE pos.person_id = 832
   AND pos.issue_category_code = 'federal_power'
   AND pos.date_start = '1830-12-09';

-- -----------------------------------------------------------------------------
-- 4) BASELINE RELATIONSHIPS — Hamilton's pole of the Nullifier coalition
-- -----------------------------------------------------------------------------
-- (685,832) legal_connection and political_alliance already exist from slice 01.
-- Add Hamilton's ties to Calhoun (272) and McDuffie (176) — the inner ring of
-- the Nullifier leadership. low<high enforced.

-- Hamilton ↔ Calhoun (272 < 832): the senior partnership of the Nullifier project
INSERT OR IGNORE INTO relationships (
    person_low_id, person_high_id, relationship_type_code,
    start_date, end_date, strength, alignment_status_code, source_id, notes
) VALUES (
    272, 832, 'political_alliance',
    '1820-01-01', '1850-03-31', 3, 'aligned', 9,
    'Calhoun the doctrinaire and Hamilton the mobilizer — Calhoun authors the South Carolina Exposition (1828) anonymously while Vice President; Hamilton organizes the public Nullifier campaign in Charleston and as governor. End_date marks Calhoun''s death (Mar 31, 1850).'
);

-- Hamilton ↔ McDuffie (176 < 832): co-anchors of the upcountry/lowcountry
-- Nullifier coalition. McDuffie (Edgefield) carries the upcountry; Hamilton
-- carries Charleston.
INSERT OR IGNORE INTO relationships (
    person_low_id, person_high_id, relationship_type_code,
    start_date, end_date, strength, alignment_status_code, source_id, notes
) VALUES (
    176, 832, 'political_alliance',
    '1825-01-01', '1851-03-11', 3, 'aligned', 9,
    'Hamilton (Charleston) and McDuffie (Edgefield) operate as the lowcountry/upcountry Nullifier counterpart to the Petigru–Perry Unionist axis. End_date marks McDuffie''s death (Mar 11, 1851).'
);

-- Hamilton ↔ Perry (2 < 832): the cross-region Nullifier-vs-Unionist tie that
-- will be characterized as fractured during the Crisis. Even when no prior
-- positive alliance existed, we record the political pairing so the renderer
-- can color the fracture during 1830–1833.
INSERT OR IGNORE INTO relationships (
    person_low_id, person_high_id, relationship_type_code,
    start_date, end_date, strength, alignment_status_code, source_id, notes
) VALUES (
    2, 832, 'political_alliance',
    '1828-01-01', '1857-11-15', 1, 'fractured', 9,
    'Recorded as a political pairing rather than a prior alliance: Perry (upcountry Unionist, Greenville) and Hamilton (lowcountry Nullifier, Charleston) sat on opposite sides of the SC fault from the moment Perry entered politics. End_date marks Hamilton''s death; the issue-specific fracture is detailed in relationship_characterizations.'
);

-- -----------------------------------------------------------------------------
-- 5) RELATIONSHIP CHARACTERIZATIONS — issue-dated alignment shifts
-- -----------------------------------------------------------------------------
-- The Petigru–Hamilton fracture row (rc 4) is already in place from slice 01.
-- This slice adds Hamilton's other 1830–1833 ties.

-- ALIGNMENT: Hamilton ↔ Calhoun on nullification, 1828–1833
INSERT OR IGNORE INTO relationship_characterizations (
    relationship_id, event_id, date_start, date_end,
    issue_category_code, scale_level_code, alignment_status_code, strength,
    relchar_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT
    (SELECT relationship_id FROM relationships
      WHERE person_low_id = 272 AND person_high_id = 832
        AND relationship_type_code = 'political_alliance'),
    (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
    '1828-12-01', '1833-03-15',
    'nullification', 'state', 'aligned', 3,
    'During the Crisis Calhoun and Hamilton operate as a coordinated leadership: Calhoun supplies the constitutional doctrine (Exposition and Protest, Fort Hill Address) while Hamilton drives the political organization in SC. They coordinate strategy through the Force Bill / Compromise Tariff endgame.',
    'observed', 3, 'mixed', 0,
    9,
    'See relchar_notes (Phase 1 dual-write, 2026-06-04).';

INSERT OR IGNORE INTO relchar_sources (relationship_characterization_id, source_id, source_role, notes)
SELECT rc.relationship_characterization_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — Calhoun-Hamilton coordination during the Crisis.'
  FROM relationship_characterizations rc
  JOIN relationships r ON r.relationship_id = rc.relationship_id
 WHERE r.person_low_id = 272 AND r.person_high_id = 832
   AND rc.issue_category_code = 'nullification'
   AND rc.date_start = '1828-12-01';

-- ALIGNMENT: Hamilton ↔ McDuffie on nullification, 1828–1833
INSERT OR IGNORE INTO relationship_characterizations (
    relationship_id, event_id, date_start, date_end,
    issue_category_code, scale_level_code, alignment_status_code, strength,
    relchar_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT
    (SELECT relationship_id FROM relationships
      WHERE person_low_id = 176 AND person_high_id = 832
        AND relationship_type_code = 'political_alliance'),
    (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
    '1828-12-01', '1833-03-15',
    'nullification', 'state', 'aligned', 3,
    'McDuffie''s upcountry Nullifier oratory (Edgefield, US House) underwrites Hamilton''s Charleston organization; together they constitute the cross-regional Nullifier coalition that the Petigru–Perry Unionist axis forms against.',
    'observed', 3, 'mixed', 0,
    9,
    'See relchar_notes (Phase 1 dual-write, 2026-06-04).';

INSERT OR IGNORE INTO relchar_sources (relationship_characterization_id, source_id, source_role, notes)
SELECT rc.relationship_characterization_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — McDuffie-Hamilton upcountry/lowcountry Nullifier coordination.'
  FROM relationship_characterizations rc
  JOIN relationships r ON r.relationship_id = rc.relationship_id
 WHERE r.person_low_id = 176 AND r.person_high_id = 832
   AND rc.issue_category_code = 'nullification'
   AND rc.date_start = '1828-12-01';

-- FRACTURE: Hamilton ↔ Perry on nullification, 1830–1833
INSERT OR IGNORE INTO relationship_characterizations (
    relationship_id, event_id, date_start, date_end,
    issue_category_code, scale_level_code, alignment_status_code, strength,
    relchar_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT
    (SELECT relationship_id FROM relationships
      WHERE person_low_id = 2 AND person_high_id = 832
        AND relationship_type_code = 'political_alliance'),
    (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
    '1830-07-01', '1833-03-15',
    'nullification', 'state', 'fractured', 3,
    'Perry''s upcountry Unionism (Greenville) confronts Hamilton''s Charleston-anchored Nullifier project across the lowcountry/upcountry divide. The fracture is structural for Perry''s public career — the Greenville Mountaineer''s editorial line is built around it.',
    'observed', 3, 'mixed', 0,
    9,
    'See relchar_notes (Phase 1 dual-write, 2026-06-04).';

INSERT OR IGNORE INTO relchar_sources (relationship_characterization_id, source_id, source_role, notes)
SELECT rc.relationship_characterization_id, 9, 'primary', 'Neumann, Bloody Flag of Anarchy — Perry''s Greenville Mountaineer editorials against Hamilton''s gubernatorial Nullifier program.'
  FROM relationship_characterizations rc
  JOIN relationships r ON r.relationship_id = rc.relationship_id
 WHERE r.person_low_id = 2 AND r.person_high_id = 832
   AND rc.issue_category_code = 'nullification'
   AND rc.date_start = '1830-07-01';

-- =============================================================================
COMMIT;

-- -----------------------------------------------------------------------------
-- VERIFICATION QUERIES — run these manually after the script:
-- -----------------------------------------------------------------------------
-- .headers on
-- .mode column
-- SELECT position_id, issue_category_code, date_start, date_end,
--        position_label_code, stance_code, substr(position_notes,1,80) AS notes_preview
--   FROM positions WHERE person_id = 832 ORDER BY date_start;
-- SELECT * FROM person_place_residence WHERE person_id = 832 ORDER BY date_start;
-- SELECT rc.relationship_characterization_id, r.person_low_id, r.person_high_id,
--        rc.issue_category_code, rc.date_start, rc.alignment_status_code,
--        substr(rc.relchar_notes,1,80) AS notes_preview
--   FROM relationship_characterizations rc
--   JOIN relationships r ON r.relationship_id = rc.relationship_id
--  WHERE r.person_low_id = 832 OR r.person_high_id = 832;
-- =============================================================================
