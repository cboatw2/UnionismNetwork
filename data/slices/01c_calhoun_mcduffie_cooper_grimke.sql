-- =============================================================================
-- Slice 01c — Calhoun, McDuffie, Cooper enrichment + Grimké legacy cleanup
-- Companion to 01_nullification_1830_1833_petigru.sql and 01b extension.
-- Adds the nullifier intellectual triumvirate (Calhoun / McDuffie / Cooper)
-- as fully coded positions and biographies, plus cleans the legacy Grimké
-- position_id=1 row inherited from the MVP seed.
-- =============================================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- -----------------------------------------------------------------------------
-- 1) BIOGRAPHICAL ENRICHMENT
-- -----------------------------------------------------------------------------
-- Thomas Cooper (person_id 683) — SC College president; midlands radical;
-- the chapter situates him as the intellectual driver of nullification's
-- secular-republican wing.  NER stub "Cooper" had no fields.
UPDATE people
SET full_name = 'Thomas Cooper',
    display_name = 'Thomas Cooper',
    gender = 'Male',
    birth_year = 1759,
    death_year = 1839,
    home_region_sc_code = 'midlands',
    occupation = 'College president / political economist',
    notes = COALESCE(NULLIF(notes,''), '') ||
            CASE WHEN COALESCE(notes,'') = '' THEN '' ELSE ' | ' END ||
            'English-born radical; president of South Carolina College 1820-1834; ' ||
            'his 1827 "Value of the Union" speech ("calculate the value of the Union") ' ||
            'helped license secular nullifier doctrine.  Petigru considered him ' ||
            'doctrinally dangerous; the College pulpit made midlands cadre receptive ' ||
            'to Calhoun-McDuffie constitutional theory.  Died May 11, 1839. ' ||
            '[Freehling, Prelude to Civil War; Sinha, Counterrevolution of Slavery]'
WHERE person_id = 683
  AND (full_name IS NULL OR full_name = 'Cooper');

-- John C. Calhoun (person_id 272)
UPDATE people
SET birth_year = 1782,
    death_year = 1850,
    gender = COALESCE(gender, 'Male'),
    home_region_sc_code = COALESCE(home_region_sc_code, 'upcountry'),
    occupation = COALESCE(occupation, 'US Senator / Vice President / political theorist'),
    notes = COALESCE(NULLIF(notes,''), '') ||
            CASE WHEN COALESCE(notes,'') = '' THEN '' ELSE ' | ' END ||
            'Author of the South Carolina Exposition and Protest (1828, anonymous) ' ||
            'and the Fort Hill Address (1831).  By 1830 the principal theorist of ' ||
            'nullification; resigned the Vice Presidency Dec 1832.  Personal antagonist ' ||
            'of Petigru in constitutional theory if not always in social life.  ' ||
            'Died Mar 31, 1850. [Freehling, Prelude to Civil War; Ford, Reconsidering Petigru]'
WHERE person_id = 272
  AND (birth_year IS NULL OR death_year IS NULL);

-- George McDuffie (person_id 176)
UPDATE people
SET birth_year = 1790,
    death_year = 1851,
    gender = COALESCE(gender, 'Male'),
    home_region_sc_code = COALESCE(home_region_sc_code, 'upcountry'),
    occupation = COALESCE(occupation, 'US Congressman / SC Governor / orator'),
    notes = COALESCE(NULLIF(notes,''), '') ||
            CASE WHEN COALESCE(notes,'') = '' THEN '' ELSE ' | ' END ||
            'Edgefield-Abbeville cadre; protégé of Calhoun.  Began as a national ' ||
            'republican who in 1821 attacked states-rights doctrine, then reversed ' ||
            'by 1825-1828 to become the most theatrical nullifier orator on the ' ||
            'House floor.  Governor of SC 1834-1836; US Senator 1842-1846. ' ||
            'Died Mar 11, 1851. [Freehling, Prelude to Civil War]'
WHERE person_id = 176
  AND (birth_year IS NULL OR death_year IS NULL);

-- -----------------------------------------------------------------------------
-- 2) POSITIONS — Calhoun
-- -----------------------------------------------------------------------------
-- Exposition & Protest window: drafted Nov 1828, debated through Webster-Hayne
-- and Jefferson Day toast (1830 Apr).  Treat as a single position spanning
-- 1828 doctrine through the 1832 Ordinance.
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 272, '1828-11-01', '1832-11-23', 'nullification', 'nullifier',
       'state', 'upcountry', 'supports',
       'Authored anonymous South Carolina Exposition and Protest (Nov 1828); ' ||
       'Fort Hill Address (Jul 1831) made his nullifier theory public; ' ||
       'Ordinance of Nullification adopted Nov 24, 1832 was the political ' ||
       'embodiment.  Petigru saw this doctrine as constitutional sophistry. [ch.fn 33-37]',
       'observed', 3, 'mixed', 0, 14,
       'Freehling, Prelude to Civil War, ch. 7-10.  Calhoun''s authorship of ' ||
       'the Exposition established the doctrinal frame the rest of the cadre executed.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 272 AND issue_category_code = 'nullification'
     AND date_start = '1828-11-01'
);

-- Radical phase during Crisis proper.
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 272, '1832-11-24', '1833-03-15', 'nullification', 'radical_nullifier',
       'state', 'upcountry', 'supports',
       'After resigning the Vice Presidency (Dec 28, 1832) Calhoun took his ' ||
       'Senate seat to defend the Ordinance directly against Webster and Jackson''s ' ||
       'Force Bill, before backing Clay''s compromise tariff. [ch.fn 38-40]',
       'observed', 3, 'mixed', 0, 14,
       'Freehling, Prelude to Civil War, ch. 14-16.  Calhoun''s shift from theorist ' ||
       'to floor leader during the Crisis itself.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 272 AND issue_category_code = 'nullification'
     AND date_start = '1832-11-24'
);

-- Federal power: post-Crisis states-rights continuation through 1850.
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 272, '1833-03-16', '1850-03-31', 'federal_power', 'states_rights_unionist',
       'national', 'upcountry', 'opposes',
       'Post-Crisis Calhoun pivots from open nullification to long-form ' ||
       'states-rights constitutionalism (concurrent majority, Discourse on the ' ||
       'Constitution).  He opposes Jacksonian and Whig consolidation alike; ' ||
       'his last major speech (Mar 1850) urges Southern resistance short of secession. [ch.fn 36]',
       'observed', 3, 'mixed', 0, 14,
       'Freehling, Prelude to Civil War; Ford, Reconsidering Petigru.  ' ||
       'Calhoun''s federal_power stance across the long 1830s-40s anchors ' ||
       'the opposite pole from Petigru on the same issue.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 272 AND issue_category_code = 'federal_power'
     AND date_start = '1833-03-16'
);

-- -----------------------------------------------------------------------------
-- 3) POSITIONS — McDuffie
-- -----------------------------------------------------------------------------
-- Early national-republican phase (the 1821 "Trio" pamphlets attacking states' rights).
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 176, '1821-01-01', '1824-12-31', 'federal_power', 'constitutional_unionist',
       'national', 'upcountry', 'supports',
       'Early McDuffie was a Calhoun-style national republican; his 1821 "Trio" ' ||
       'essays attacked Crawford-Smith states-rights doctrine.  This phase ' ||
       'sets up the dramatic 1828-1832 reversal Petigru cites as proof that ' ||
       'nullifier doctrine was opportunist, not principled. [ch.fn 33]',
       'observed', 2, 'mixed', 1, 14,
       'Freehling, Prelude to Civil War, ch. 5.  McDuffie''s reversal is the ' ||
       'paradigmatic case of upcountry cadre conversion.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 176 AND issue_category_code = 'federal_power'
     AND date_start = '1821-01-01'
);

-- Crisis-phase nullifier; the floor orator.
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 176, '1828-05-19', '1833-03-15', 'nullification', 'radical_nullifier',
       'state', 'upcountry', 'supports',
       'After the Tariff of Abominations (May 1828) McDuffie reversed his earlier ' ||
       'nationalism and became the cadre''s most theatrical orator ("Forty Bale" ' ||
       'theory, 1830).  House floor leader for nullification through the Crisis. [ch.fn 33-35]',
       'observed', 3, 'mixed', 0, 14,
       'Freehling, Prelude to Civil War, ch. 9-12.  McDuffie''s reversal and ' ||
       'rhetorical leadership in 1828-1833 are central to the radical phase.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 176 AND issue_category_code = 'nullification'
     AND date_start = '1828-05-19'
);

-- Slavery / economy linkage — McDuffie's 1835 governor's address calling
-- slavery a "positive good."  Records the ideological hardening Petigru
-- documents in his post-1834 correspondence.
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 176, '1835-11-24', '1836-12-31', 'slavery', 'states_rights_unionist',
       'state', 'upcountry', 'supports',
       'Governor''s annual message Nov 1835 declared slavery a positive good and ' ||
       'called for criminalizing abolitionist literature.  Marks the post-Crisis ' ||
       'shift of nullifier energy onto slavery defense. [ch.fn 60]',
       'observed', 3, 'direct_quote', 0, 15,
       'Sinha, Counterrevolution of Slavery.  McDuffie''s 1835 message is the ' ||
       'textbook articulation of the slavery-positive-good doctrine.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 176 AND issue_category_code = 'slavery'
     AND date_start = '1835-11-24'
);

-- -----------------------------------------------------------------------------
-- 4) POSITIONS — Cooper
-- -----------------------------------------------------------------------------
-- His 1827 "Value of the Union" speech precedes the formal nullification
-- doctrine but the chapter treats it as the secular-republican license for it.
INSERT OR IGNORE INTO positions
  (person_id, date_start, date_end, issue_category_code, position_label_code,
   scale_level_code, region_relevance_code, stance_code, position_notes,
   claim_type_code, confidence_score, evidence_type_code,
   counterevidence_present, source_id, justification_note)
SELECT 683, '1827-07-02', '1827-12-31', 'federal_power', 'nullifier',
       'state', 'midlands', 'opposes',
       'Columbia speech Jul 2, 1827: "It is time to calculate the value of the ' ||
       'Union."  The midlands secular-republican opening salvo for separation- ' ||
       'doctrine, predating Calhoun''s Exposition by a year. [ch.fn 30-31]',
       'observed', 3, 'direct_quote', 0, 14,
       'Freehling, Prelude to Civil War, ch. 6.  Cooper''s speech is treated as ' ||
       'the pivot from grievance to doctrine.'
WHERE NOT EXISTS (
  SELECT 1 FROM positions
   WHERE person_id = 683 AND issue_category_code = 'federal_power'
     AND date_start = '1827-07-02'
);

-- The slice 01b position (id 18) already covers 1828-1834 nullification/nullifier.
-- No additional row needed there.

-- -----------------------------------------------------------------------------
-- 5) GRIMKÉ LEGACY POSITION CLEANUP (position_id = 1)
-- -----------------------------------------------------------------------------
-- The original MVP seed row has no stance_code / dates / source_id, leaving
-- it floating in time and uncoded by the visualizer.  The chapter narrative
-- it referenced is the 1832 Southern Convention dispute (Sept-Dec 1832),
-- where Grimké refused to endorse the unionist call for a southern convention.
-- Backfill the row in place so the unique "Southern Convention disagreement"
-- claim is preserved distinct from the broad 1830-1834 position (id 17).
UPDATE positions
SET date_start = '1832-09-01',
    date_end = '1832-12-31',
    scale_level_code = COALESCE(scale_level_code, 'state'),
    region_relevance_code = COALESCE(region_relevance_code, 'lowcountry'),
    stance_code = 'qualified',
    source_id = 6,
    position_notes = COALESCE(position_notes, '') ||
        CASE WHEN COALESCE(position_notes,'') = '' THEN '' ELSE ' | ' END ||
        'Refused the unionist push for a Southern Convention in autumn 1832; ' ||
        'opposed nullification doctrine while declining the compromise mechanism ' ||
        'that more pragmatic unionists (Petigru, Huger, Legaré) advanced. ' ||
        'A qualified-opposes posture distinct from his 1834 McCready stance.'
WHERE position_id = 1
  AND person_id = 730
  AND stance_code IS NULL;

-- -----------------------------------------------------------------------------
-- 6) VERIFICATION (run manually)
-- -----------------------------------------------------------------------------
-- SELECT person_id, full_name, birth_year, death_year FROM people WHERE person_id IN (176, 272, 683);
-- SELECT position_id, person_id, issue_category_code, date_start, date_end, position_label_code, stance_code
--   FROM positions WHERE person_id IN (176, 272, 683, 730) ORDER BY person_id, date_start;

COMMIT;
