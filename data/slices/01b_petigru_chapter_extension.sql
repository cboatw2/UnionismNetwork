-- =============================================================================
-- Slice 01b — PETIGRU CHAPTER EXTENSION (drawn from dissertation chapter draft)
-- =============================================================================
-- Purpose: deepen slice 01 (1830–1833 Petigru core) with the people, sources,
-- positions, and relationships attested in the user's Petigru dissertation
-- chapter ("Dissertation (1).txt"). Where the chapter cites a specific footnote
-- the corresponding row's notes column carries a "[ch.fn N]" tag so any future
-- audit can trace each datum back to the prose.
--
-- This slice is RE-RUNNABLE (INSERT OR IGNORE + NOT EXISTS guards), matching
-- the convention established in slices 01 and 02. To "rewrite" a claim, delete
-- the offending row by id first and re-run.
--
-- VERIFIED IDs as of 2026-06-04:
--   people:  685 Petigru, 832 Hamilton Jr., 2 Perry, 4 Hugh Legaré,
--            94 Daniel Elliott Huger, 507 William John Grayson,
--            730 Thomas Grimké, 3 Joel Roberts Poinsett, 5 William Drayton,
--            1082 Benjamin Fanieul Hunt, 272 John C. Calhoun,
--            176 George McDuffie, 683 Cooper (Thomas Cooper, SCC president),
--            584 Jane Amelia Postell Petigru
--   places:  5 Charleston, 6 Columbia, 7 Greenville, 8 Abbeville,
--            10 Washington, 12 Eutaw, 13 Beaufort, 14 Flat Woods, 15 Badwell
--   sources: 6 Pease, 7 Grayson Witness To Sorrow, 8 Carson 1920 (added by
--            slice 01), 9 Neumann Bloody Flag
--
-- BACK UP unionism.db BEFORE RUNNING:
--   cp unionism.db unionism.db.bak_pre_petigru_extension_$(date +%Y%m%d_%H%M%S)
-- THEN:
--   sqlite3 unionism.db < data/slices/01b_petigru_chapter_extension.sql
-- =============================================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- -----------------------------------------------------------------------------
-- 1) SOURCES — secondary works cited in the Petigru chapter
-- -----------------------------------------------------------------------------
INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Reconsidering James Petigru: Unionist and Civic Reformer in a Radical Age',
       'Lacy K. Ford',
       '2021',
       'South Carolina Historical Magazine 122.3',
       'Ford, Lacy K. "Reconsidering James Petigru: Unionist and Civic Reformer in a Radical Age." South Carolina Historical Magazine 122, no. 3 (2021): 124-152.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'Reconsidering James Petigru: Unionist and Civic Reformer in a Radical Age');

INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'South Carolina: A History',
       'Walter B. Edgar',
       '1998',
       'University of South Carolina Press',
       'Edgar, Walter B. South Carolina: A History. Columbia, S.C.: University of South Carolina Press, 1998.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'South Carolina: A History');

INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Benjamin F. Perry, South Carolina Unionist',
       'Lillian Adele Kibler',
       '1946',
       'Duke University Press',
       'Kibler, Lillian Adele. Benjamin F. Perry, South Carolina Unionist. Durham, N.C.: Duke University Press, 1946.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'Benjamin F. Perry, South Carolina Unionist');

INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Honor and Violence in the Old South',
       'Bertram Wyatt-Brown',
       '1986',
       'Oxford University Press',
       'Wyatt-Brown, Bertram. Honor and Violence in the Old South. New York: Oxford University Press, 1986.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'Honor and Violence in the Old South');

INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Prelude to Civil War: The Nullification Controversy in South Carolina, 1816-1836',
       'William W. Freehling',
       '1965',
       'Oxford University Press',
       'Freehling, William W. Prelude to Civil War: The Nullification Controversy in South Carolina, 1816-1836. New York: Oxford University Press, 1965.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'Prelude to Civil War: The Nullification Controversy in South Carolina, 1816-1836');

INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'The Counterrevolution of Slavery: Politics and Ideology in Antebellum South Carolina',
       'Manisha Sinha',
       '2000',
       'University of North Carolina Press',
       'Sinha, Manisha. The Counterrevolution of Slavery: Politics and Ideology in Antebellum South Carolina. Chapel Hill: University of North Carolina Press, 2000.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'The Counterrevolution of Slavery: Politics and Ideology in Antebellum South Carolina');

INSERT INTO sources (source_type_code, title, creator, date_created, archive, citation_full)
SELECT 'secondary',
       'Southern Cross: The Beginnings of the Bible Belt',
       'Christine Leigh Heyrman',
       '1997',
       'University of North Carolina Press',
       'Heyrman, Christine Leigh. Southern Cross: The Beginnings of the Bible Belt. Chapel Hill: University of North Carolina Press, 1997.'
WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = 'Southern Cross: The Beginnings of the Bible Belt');

-- -----------------------------------------------------------------------------
-- 2) PLACES — geography the chapter references but DB does not yet have
-- -----------------------------------------------------------------------------
INSERT INTO places (place_name, place_type_code, latitude, longitude, region_sc_code, modern_state, notes)
SELECT 'Coosawhatchie', 'town', 32.5946, -80.9756, 'lowcountry', 'SC',
       'Court town of Beaufort District; Petigru began his law practice here 1812-1819. [ch.fn 13-14]'
WHERE NOT EXISTS (SELECT 1 FROM places WHERE place_name = 'Coosawhatchie');

INSERT INTO places (place_name, place_type_code, latitude, longitude, region_sc_code, modern_state, notes)
SELECT 'Willington', 'town', 33.9846, -82.4565, 'upcountry', 'SC',
       'Site of Moses Waddel''s academy (Willington Academy) in Abbeville District; Petigru entered Oct 1804. [ch.fn 3, 7]'
WHERE NOT EXISTS (SELECT 1 FROM places WHERE place_name = 'Willington');

INSERT INTO places (place_name, place_type_code, latitude, longitude, region_sc_code, modern_state, notes)
SELECT 'Summerville', 'town', 33.0185, -80.1756, 'lowcountry', 'SC',
       'Petigru retreat outside Charleston; he wrote his 1862 Caroline letter from here recounting Waddel''s academy. [ch.fn 7]'
WHERE NOT EXISTS (SELECT 1 FROM places WHERE place_name = 'Summerville');

INSERT INTO places (place_name, place_type_code, latitude, longitude, region_sc_code, modern_state, notes)
SELECT 'New York City', 'town', 40.7128, -74.0060, NULL, 'NY',
       'Destination for Petigru''s 1834 sending of daughter Caroline north; also refuge for other SC Unionists during Nullification reign-of-terror. [ch.fn 56-57]'
WHERE NOT EXISTS (SELECT 1 FROM places WHERE place_name = 'New York City');

INSERT INTO places (place_name, place_type_code, latitude, longitude, region_sc_code, modern_state, notes)
SELECT 'Brussels', 'town', 50.8503, 4.3517, NULL, NULL,
       'Hugh S. Legaré served as US chargé d''affaires here 1832-1836; recipient of Petigru''s Dec 1832 / Oct 1832 Nullification letters. [ch.fn 40-41, 46-48]'
WHERE NOT EXISTS (SELECT 1 FROM places WHERE place_name = 'Brussels');

-- -----------------------------------------------------------------------------
-- 3) PETIGRU BIO REFINEMENT — fields the chapter sharpens
-- -----------------------------------------------------------------------------
UPDATE people
SET notes = COALESCE(notes, '') ||
            CASE WHEN COALESCE(notes,'') = '' THEN '' ELSE ' | ' END ||
            'Conditional constitutionalist (not strict conservative): political change must come through Constitutionally-prescribed processes. Education trajectory Badwell → Waddel''s academy at Willington (Oct 1804) → South Carolina College (1806-1809, top of class) → Eutaw teaching → Beaufort College → Coosawhatchie law practice (1812-1819) → Charleston partnership with James Hamilton, Jr. (1819-). [Ford 2021; Pease & Pease]'
WHERE person_id = 685
  AND (notes IS NULL OR notes NOT LIKE '%conditional constitutionalist%');

-- -----------------------------------------------------------------------------
-- 4) NEW PEOPLE — biographical stubs for chapter-attested figures missing from DB
-- -----------------------------------------------------------------------------
-- Albert Petigru (died age 8, Sept 13, 1826, household accident in Charleston).
INSERT INTO people (full_name, display_name, gender, birth_year, death_year, home_region_sc_code, notes)
SELECT 'Albert Petigru', 'Albert Petigru', 'Male', 1818, 1826, 'lowcountry',
       'Eldest son of James L. and Jane Amelia Postell Petigru. Died Sept 13, 1826 at age 8 from a fall on the stairs of the family Charleston home while parents were absent. His death (compounded by the near-simultaneous death of Petigru''s mother at Badwell) marked an emotional crisis in the family. [ch.fn 19]'
WHERE NOT EXISTS (SELECT 1 FROM people WHERE full_name = 'Albert Petigru');

INSERT INTO people (full_name, display_name, gender, birth_year, death_year, home_region_sc_code, notes)
SELECT 'Caroline Petigru', 'Caroline Petigru', 'Female', 1819, 1893, 'lowcountry',
       'Daughter of James L. Petigru. Sent to New York City in 1834 by her father as a precaution amid the post-Nullification political climate in South Carolina; recipient of Petigru''s 1862 Summerville letter recounting Waddel''s academy. [ch.fn 7, 19, 56]'
WHERE NOT EXISTS (SELECT 1 FROM people WHERE full_name = 'Caroline Petigru');

INSERT INTO people (full_name, display_name, gender, birth_year, death_year, home_region_sc_code, occupation, notes)
SELECT 'Moses Waddel', 'Moses Waddel', 'Male', 1770, 1840, 'upcountry', 'Educator / Presbyterian minister',
       'Principal of Willington Academy in Abbeville District (5-10 miles from Badwell); Petigru entered Oct 14, 1804. Calvinist conservatism shaped Petigru''s religious-political worldview. Officiated Petigru-Postell wedding 1816. [ch.fn 3, 4, 7, 15]'
WHERE NOT EXISTS (SELECT 1 FROM people WHERE full_name = 'Moses Waddel');

INSERT INTO people (full_name, display_name, gender, home_region_sc_code, occupation, notes)
SELECT 'William Robertson (Beaufort)', 'William Robertson', 'Male', 'lowcountry', 'Lawyer',
       'Beaufort attorney under whom Petigru read law c.1810-1812; helped him pass the bar in 1812. NOT to be confused with the various Robertson NER stubs (person_id 15, 840). [ch.fn 13-14]'
WHERE NOT EXISTS (SELECT 1 FROM people WHERE full_name = 'William Robertson (Beaufort)');

INSERT INTO people (full_name, display_name, gender, home_region_sc_code, occupation, notes)
SELECT 'Edward McCready', 'Edward McCready', 'Male', 'lowcountry', 'Militia officer / litigant',
       'Charleston militia officer denied his commission for refusing the Test Oath; his appeal (argued by Petigru and Thomas S. Grimké) became the vehicle for the Unionist constitutional challenge to the Test Oath. SC Court of Appeals ruled in his favor 1834. [ch.fn 54]'
WHERE NOT EXISTS (SELECT 1 FROM people WHERE full_name = 'Edward McCready');

INSERT INTO people (full_name, display_name, gender, home_region_sc_code, occupation, notes)
SELECT 'James Haig', 'James Haig', 'Male', 'lowcountry', 'Lawyer',
       'Charleston attorney; led a 1832 National-Republican faction within the SC Unionists pushing Henry Clay''s presidential candidacy until Petigru persuaded them to fall back behind Jackson to avoid splitting the Unionist vote. [ch.fn 45]'
WHERE NOT EXISTS (SELECT 1 FROM people WHERE full_name = 'James Haig');

-- -----------------------------------------------------------------------------
-- 5) PETIGRU RESIDENCES — chapter adds Coosawhatchie, Eutaw, Willington stints
-- -----------------------------------------------------------------------------
-- Willington (Waddel's academy), Oct 1804 – mid-1806
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685,
       (SELECT place_id FROM places WHERE place_name = 'Willington'),
       'household', '1804-10-14', '1806-06-30', 8,
       'Boarded at Moses Waddel''s academy in Willington from Oct 14, 1804; left c.1806 to enter South Carolina College. [ch.fn 3, 7]'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685
      AND place_id = (SELECT place_id FROM places WHERE place_name = 'Willington')
);

-- Columbia (South Carolina College), 1806–1809
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685, 6, 'household', '1806-09-01', '1809-12-31', 8,
       'Sophomore admission to South Carolina College 1806; graduated top of class of ~80 in 1809. Lived off campus and taught at Columbia Academy to defray expenses. [ch.fn 8-10]'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685 AND place_id = 6 AND residence_type_code = 'household'
);

-- Eutaw teaching, c.1809–1810
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685, 12, 'professional_base', '1809-10-01', '1810-12-31', 6,
       'Took a teaching position at Eutaw (~50 miles SE of Columbia) directly after SCC graduation; through Daniel Huger''s patronage met the local lowcountry elite. [ch.fn 12]'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685 AND place_id = 12 AND residence_type_code = 'professional_base'
);

-- Coosawhatchie law practice, 1812–1819 (overlaps lowcountry residence in slice 01)
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685,
       (SELECT place_id FROM places WHERE place_name = 'Coosawhatchie'),
       'professional_base', '1812-01-01', '1819-12-31', 6,
       'Hung law shingle in Coosawhatchie (court town of Beaufort District) after passing the bar 1812; first three years lean. Elected solicitor for Beaufort District before Charleston partnership 1819. [ch.fn 13-14]'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685
      AND place_id = (SELECT place_id FROM places WHERE place_name = 'Coosawhatchie')
);

-- Summerville retreat (1862 dateline of Caroline letter)
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT 685,
       (SELECT place_id FROM places WHERE place_name = 'Summerville'),
       'temporary_residence', '1861-01-01', '1863-03-09', 8,
       'Used Summerville as a retreat from Confederate Charleston in the final years of his life; the Oct 14, 1862 letter to Caroline recounting his 1804 entry to Waddel''s academy is dated from here. [ch.fn 7]'
WHERE NOT EXISTS (
    SELECT 1 FROM person_place_residence
    WHERE person_id = 685
      AND place_id = (SELECT place_id FROM places WHERE place_name = 'Summerville')
      AND residence_type_code = 'temporary_residence'
);

-- -----------------------------------------------------------------------------
-- 6) PETIGRU POSITIONS — extend timeline beyond 1833
-- -----------------------------------------------------------------------------
-- 1834 Washington Society Oration: matured constitutional Unionism on federal_power.
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
       '1833-03-16', '1860-04-30',
       'federal_power', 'constitutional_unionist',
       'national', NULL,
       'supports',
       'Petigru''s July 4, 1834 oration before the Washington Society (Charleston) articulates his developed conditional constitutionalism: the Revolutionary War was secondary to the Constitution; the Constitution was a "masterpiece of wisdom" forged by the Convention of 1787 and the people''s subsequent ratification debates, and it represents the only legitimate channel for political change. The position holds steady from the Compromise of 1833 until the Charleston Democratic Convention of May 1860. [ch.fn 55]',
       'observed', 3, 'direct_quote', 0,
       8,
       'Carson 1920 prints the full Washington Society Oration, pp. 142-153. [ch.fn 55]'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'federal_power' AND date_start = '1833-03-16'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 8, 'primary', 'Carson 1920, Washington Society Oration text, pp. 142-153. [ch.fn 55]'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'federal_power' AND pos.date_start = '1833-03-16';

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id,
       (SELECT source_id FROM sources WHERE title = 'Reconsidering James Petigru: Unionist and Civic Reformer in a Radical Age'),
       'secondary',
       'Ford 2021 reads the Washington Society Oration as evidence of "conditional constitutionalism" rather than passive conservatism.'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'federal_power' AND pos.date_start = '1833-03-16';

-- 1834 McCready test-oath case — continued nullification opposition post-Compromise.
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
       '1833-03-16', '1836-12-31',
       'nullification', 'absolute_unionist',
       'state', 'lowcountry',
       'opposes',
       'After the March 1833 Compromise Tariff the Nullifiers pivoted to a Test Oath requiring state officials to swear allegiance to South Carolina above the United States. Petigru, joined by Thomas S. Grimké, represented Edward McCready (a militia officer denied his commission for refusing the oath) in McCready v. Hunt. The SC Court of Appeals ruled in McCready''s favor in 1834, but a generalized version of the test oath later entered the SC Constitution by amendment. The case is the clearest expression of Petigru''s position that nullification (and its sequelae) violated both the 1790 SC Constitution and the federal supremacy clause. [ch.fn 54]',
       'observed', 3, 'mixed', 0,
       6,
       'Pease & Pease and Ford 2021 both treat the McCready case as the post-Compromise codification of Petigru''s Unionism. [ch.fn 54]'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'nullification' AND date_start = '1833-03-16'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id,
       (SELECT source_id FROM sources WHERE title = 'Reconsidering James Petigru: Unionist and Civic Reformer in a Radical Age'),
       'primary',
       'Ford 2021, "Reconsidering James Petigru," 136-138, on the McCready case. [ch.fn 54]'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1833-03-16';

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'secondary', 'Pease & Pease, James Louis Petigru, on McCready and the Test Oath aftermath.'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1833-03-16';

-- 1860 Charleston Democratic Convention — secession axis opens; Petigru opposes
-- but with exhaustion ("contracted a disinclination to write or to speak").
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 685,
       NULL,
       '1860-05-01', '1863-03-09',
       'secession', 'absolute_unionist',
       'state', 'lowcountry',
       'opposes',
       'At the May 1860 Charleston Democratic Convention Petigru sat among SC Democrats while Perry implored the assembly to choose a Union-preserving nominee. Petigru, angered by the hissing and scoffing of his neighbors, declined to challenge them publicly "out of respect for the women present in the galleries" and afterward wrote Perry that he had "contracted a disinclination to write or to speak, when truth is in question." His Unionism persists categorically through the December 1860 Ordinance of Secession to his March 9, 1863 death in Confederate Charleston; what changes is rhetorical fight, not stance. [ch.fn 1]',
       'observed', 3, 'direct_quote', 0,
       (SELECT source_id FROM sources WHERE title = 'Benjamin F. Perry, South Carolina Unionist'),
       'Kibler 1946, Benjamin F. Perry, South Carolina Unionist, pp. 5-6; Pease & Pease, James Louis Petigru, p. 155 — both quote the post-Convention Petigru-to-Perry letter. [ch.fn 1]'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'secession' AND date_start = '1860-05-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id,
       (SELECT source_id FROM sources WHERE title = 'Benjamin F. Perry, South Carolina Unionist'),
       'primary',
       'Kibler 1946, 5-6. [ch.fn 1]'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'secession' AND pos.date_start = '1860-05-01';

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, James Louis Petigru, 155. [ch.fn 1]'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'secession' AND pos.date_start = '1860-05-01';

-- 1860 parallel federal_power claim (same source, different issue axis).
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 685,
       NULL,
       '1860-05-01', '1863-03-09',
       'federal_power', 'absolute_unionist',
       'national', NULL,
       'supports',
       'Continues 1833-1860 federal-supremacy stance into the secession crisis. Petigru never repudiates the Constitution under Confederate Charleston; he in fact codifies SC laws under Confederate auspices without abandoning his Unionism, dying March 9, 1863 in Charleston. [ch.fn 1, 57]',
       'observed', 2, 'mixed', 0,
       6,
       'Pease & Pease, James Louis Petigru, on Petigru''s wartime Charleston life and codification work.'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'federal_power' AND date_start = '1860-05-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, James Louis Petigru. [ch.fn 1, 57]'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'federal_power' AND pos.date_start = '1860-05-01';

-- 1832 personal_honor — aborted Hunt duel (placed in 1826 window).
-- Stored on personal_honor axis with stance=qualified; chapter footnote 20.
INSERT INTO positions (
    person_id, event_id, date_start, date_end,
    issue_category_code, position_label_code,
    scale_level_code, region_relevance_code,
    stance_code, position_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT 685,
       NULL,
       '1826-06-01', '1826-09-30',
       'personal_honor', 'unknown',
       'local', 'lowcountry',
       'qualified',
       'Summer 1826 duel-arrangements between Petigru and Benjamin Fanieul Hunt were well underway when Hunt withdrew the challenge upon learning of the deaths of Petigru''s son Albert and his mother. The aborted duel illustrates Petigru''s full participation in elite male honor culture AND the flexibility of that culture: Hunt''s withdrawal protected his own reputation while acknowledging Petigru''s standing. Coded "qualified" because Petigru accepted the challenge (participation in honor system) but never fired — the affair was suspended, not resolved. [ch.fn 20-21]',
       'observed', 3, 'mixed', 0,
       6,
       'Pease & Pease, James Louis Petigru, 33-34. [ch.fn 20]'
WHERE NOT EXISTS (
    SELECT 1 FROM positions
    WHERE person_id = 685 AND issue_category_code = 'personal_honor' AND date_start = '1826-06-01'
);

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, James Louis Petigru, 33-34. [ch.fn 20]'
  FROM positions pos
 WHERE pos.person_id = 685 AND pos.issue_category_code = 'personal_honor' AND pos.date_start = '1826-06-01';

-- -----------------------------------------------------------------------------
-- 7) POSITIONS for the SUPPORTING UNIONIST CAST during Nullification
-- -----------------------------------------------------------------------------
-- Each row: one issue, one dated window, one stance, sourced to chapter footnote.
-- Together these light up the 1830-1833 Charleston Unionist cluster on the
-- visualization (Petigru-Legaré-Huger-Grayson-Grimké-Poinsett-Drayton).

-- Daniel Elliott Huger (94) — Unionist co-leader Charleston, 1830 city election.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 94, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15', 'nullification', 'constitutional_unionist', 'state', 'lowcountry', 'opposes',
       'Huger co-led the Charleston Union Party in the 1830 city council election alongside Petigru, opposed by the Nullifier ticket headed by Robert Y. Hayne and James Hamilton, Jr. Long-standing patron of Petigru since the Eutaw/Beaufort years; the 1830 alliance was the political extension of a personal one. [ch.fn 12, 36]',
       'observed', 3, 'mixed', 0, 6, 'Pease & Pease, James Louis Petigru, 41-43; Kibler 1946 on Huger as Perry''s mentor as well. [ch.fn 12, 36]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 94 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, 41-43. [ch.fn 36]' FROM positions pos WHERE pos.person_id = 94 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- Hugh Legaré (4) — Petigru's closest political correspondent; AG successor; Brussels.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 4, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15', 'nullification', 'constitutional_unionist', 'state', 'lowcountry', 'opposes',
       'Legaré resigned his SC lower-house seat in 1830 to take up the attorney generalship vacated by Petigru, freeing Petigru to run for (and win) Legaré''s house seat. As US chargé d''affaires in Brussels (1832-1836) he received Petigru''s extended Nullification correspondence (Oct 1832, Dec 1832, Mar 1833) which is the documentary spine of Petigru''s recorded stance. [ch.fn 37, 40-41, 46-48, 53]',
       'observed', 3, 'direct_quote', 0, 8, 'Carson 1920 prints the full Petigru-Legaré correspondence series. [ch.fn 40-41]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 4 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 8, 'primary', 'Carson 1920 — Petigru-Legaré letters. [ch.fn 40-41]' FROM positions pos WHERE pos.person_id = 4 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- William John Grayson (507) — Unionist; later Petigru biographer (1866).
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 507, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15', 'nullification', 'constitutional_unionist', 'state', 'lowcountry', 'opposes',
       'Waddel''s academy classmate of Petigru and Legaré; Unionist during Nullification. Later authored the 1866 biographical sketch of Petigru that frames the Calhoun-vs-Smith struggle of the 1820s as a "mere game for power" — a downplaying the chapter draft critiques. [ch.fn 6, 23-24]',
       'observed', 2, 'mixed', 0, 7, 'Grayson, James Louis Petigru: A Biographical Sketch (1866), 92-93. [ch.fn 24]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 507 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 7, 'primary', 'Grayson biographical sketch. [ch.fn 24]' FROM positions pos WHERE pos.person_id = 507 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- Thomas S. Grimké (730) — McCready case co-counsel with Petigru.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 730, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1834-10-12', 'nullification', 'absolute_unionist', 'state', 'lowcountry', 'opposes',
       'Charleston attorney; co-counsel with Petigru in McCready v. Hunt (1834), arguing the Test Oath violated both the 1790 SC Constitution and the federal supremacy clause. Death (cholera, Oct 12, 1834) closes the active window. [ch.fn 54]',
       'observed', 3, 'mixed', 0, 6, 'Pease & Pease, James Louis Petigru on the McCready case; Ford 2021, 136-138. [ch.fn 54]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 730 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease + Ford 2021 on McCready. [ch.fn 54]' FROM positions pos WHERE pos.person_id = 730 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- Joel R. Poinsett (3) — Jackson's eyes-and-ears in Charleston; struck in 1832 election violence.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 3, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15', 'nullification', 'absolute_unionist', 'state', 'lowcountry', 'opposes',
       'Charleston Unionist leader; channel between SC Unionists and President Jackson; physically struck during the October 1832 Charleston street violence Petigru described to Legaré. [ch.fn 48, 52, 57]',
       'observed', 3, 'mixed', 0, 8, 'Carson 1920 reproduces the Petigru-Legaré Oct 29, 1832 letter naming Poinsett as struck. [ch.fn 48]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 3 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 8, 'primary', 'Carson 1920, Petigru-Legaré Oct 1832. [ch.fn 48]' FROM positions pos WHERE pos.person_id = 3 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- William Drayton (5) — also struck in 1832 election violence; Hamilton inherited his firm.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 5, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15', 'nullification', 'constitutional_unionist', 'state', 'lowcountry', 'opposes',
       'Drayton''s Charleston law firm was the one Hamilton inherited (1818) and Petigru later joined (1819); a senior Charleston Unionist publicly struck during the October 1832 election violence. [ch.fn 16, 48]',
       'observed', 2, 'mixed', 0, 8, 'Carson 1920, Petigru-Legaré Oct 1832. [ch.fn 48]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 5 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 8, 'primary', 'Carson 1920. [ch.fn 48]' FROM positions pos WHERE pos.person_id = 5 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- Benjamin F. Hunt (1082) — Unionist on the constitutional question, but pro-tariff;
-- aborted-duel partner with Petigru in 1826; the 1831 pamphlet damaged Unionist messaging.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 1082, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15', 'nullification', 'mixed_alignment', 'state', 'lowcountry', 'opposes',
       'Massachusetts-born Charleston attorney; nominally Unionist on the constitutional question but unusual in defending the tariff itself ("unluckily" stepped "over the line"), which Petigru blamed for collapsing Unionist messaging in 1831. Coded mixed_alignment to capture the tariff/nullification cross-pressure. [ch.fn 38]',
       'observed', 2, 'mixed', 1, 8, 'Carson 1920, Petigru-Elliot Aug 25, 1831 (Hunt pamphlet criticism). [ch.fn 38]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 1082 AND issue_category_code = 'nullification' AND date_start = '1830-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 8, 'primary', 'Carson 1920, Petigru-Elliot Aug 1831. [ch.fn 38]' FROM positions pos WHERE pos.person_id = 1082 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1830-01-01';

-- Thomas Cooper (683) — SC College president; ideological architect of disunion; Petigru's 1832 removal target.
INSERT INTO positions (person_id, event_id, date_start, date_end, issue_category_code, position_label_code, scale_level_code, region_relevance_code, stance_code, position_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT 683, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1828-01-01', '1834-12-31', 'nullification', 'nullifier', 'state', 'midlands', 'supports',
       'President of South Carolina College and ideological cultivator of disunion sentiment for two decades; the target of Petigru''s 1832 SC senate legislation seeking his removal on grounds of anticlerical deism — bill failed but college board investigation contributed to Cooper''s 1834 resignation. [ch.fn 27, 42-43]',
       'observed', 2, 'mixed', 0, (SELECT source_id FROM sources WHERE title = 'South Carolina: A History'), 'Edgar, South Carolina, 326-329 on Cooper''s disunionist influence; Pease & Pease, 47-48 on the 1832 removal effort. [ch.fn 27, 42]'
WHERE NOT EXISTS (SELECT 1 FROM positions WHERE person_id = 683 AND issue_category_code = 'nullification' AND date_start = '1828-01-01');

INSERT OR IGNORE INTO position_sources (position_id, source_id, source_role, notes)
SELECT pos.position_id, 6, 'primary', 'Pease & Pease, 47-48. [ch.fn 42]' FROM positions pos WHERE pos.person_id = 683 AND pos.issue_category_code = 'nullification' AND pos.date_start = '1828-01-01';

-- -----------------------------------------------------------------------------
-- 8) RELATIONSHIPS — Petigru's inner circle (and rivals) — baseline rows
-- -----------------------------------------------------------------------------
-- Convention: relationships.person_low_id < person_high_id.
-- For each, an issue-specific relationship_characterizations row follows in (9).

-- Petigru (685) ↔ Hugh Legaré (4)
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (4, 685, 'friendship', '1804-10-01', '1843-06-20', 3, 'aligned', 8,
        'Boyhood friendship from Waddel''s academy; extended through SCC, Charleston bar, AG-relay (1830), and Legaré''s Brussels chargé tenure (1832-1836); ends with Legaré''s 1843 death. [ch.fn 6, 37]');

INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (4, 685, 'correspondence', '1830-01-01', '1843-06-20', 3, 'aligned', 8,
        'Carson 1920 prints the bulk of the surviving Petigru-Legaré correspondence; the Oct/Dec 1832 and Mar 1833 letters are the spine of Petigru''s recorded Nullification stance. [ch.fn 40-41, 46, 48, 53]');

-- Petigru (685) ↔ Daniel E. Huger (94)
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (94, 685, 'political_alliance', '1810-01-01', '1854-08-21', 3, 'aligned', 6,
        'Huger befriended Petigru as a young Eutaw teacher; secured his Beaufort College position; supported his early law career; co-led the 1830 Charleston Unionist city ticket. End_date = Huger''s death. [ch.fn 12, 36]');

-- Petigru (685) ↔ William J. Grayson (507)
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (507, 685, 'friendship', '1804-10-01', '1863-03-09', 3, 'aligned', 7,
        'Waddel''s academy classmate; lifelong Charleston peer and fellow Unionist; later author of the 1866 biographical sketch of Petigru. [ch.fn 6]');

-- Petigru (685) ↔ Thomas Grimké (730) — legal collaboration
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (685, 730, 'legal_connection', '1833-01-01', '1834-10-12', 3, 'aligned', 6,
        'Co-counsel with Petigru in McCready v. Hunt (SC Court of Appeals, 1834) challenging the Nullifier Test Oath. End_date = Grimké''s death (cholera). [ch.fn 54]');

-- Petigru (685) ↔ Joel R. Poinsett (3)
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (3, 685, 'political_alliance', '1830-01-01', '1851-12-12', 3, 'aligned', 8,
        'Charleston Unionist co-leaders during Nullification; both physically struck in the October 1832 election violence per Petigru-Legaré Oct 1832 letter. End_date = Poinsett''s death. [ch.fn 48]');

-- Petigru (685) ↔ William Drayton (5)
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (5, 685, 'political_alliance', '1830-01-01', '1846-05-24', 2, 'aligned', 8,
        'Senior Charleston Unionist whose firm Hamilton inherited (1818) and Petigru later joined (1819); Unionist co-figure struck in the Oct 1832 election violence. End_date = Drayton''s death. [ch.fn 16, 48]');

-- Petigru (685) ↔ Benjamin F. Hunt (1082) — aborted-duel + ideological cross-pressure
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (685, 1082, 'professional', '1820-01-01', '1857-12-31', 2, 'strained', 6,
        'Charleston-bar peers; their relationship is structured by the suspended 1826 duel (Hunt withdrew on news of Petigru''s son''s death) and the 1831 pro-tariff pamphlet that Petigru blamed for Unionist losses. Strained, not fractured: still nominally on the same side on nullification, in opposition on tariff. [ch.fn 20, 38]');

-- Petigru (685) ↔ John C. Calhoun (272) — fractures over nullification
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (272, 685, 'ideological_conflict', '1828-01-01', '1850-03-31', 3, 'adversarial', 6,
        'Calhoun''s pivot to states-rights doctrine after the Jackson-Calhoun fallout placed him in direct ideological opposition to Petigru''s conditional constitutionalism throughout Nullification and beyond. End_date = Calhoun''s death. [ch.fn 25-26, 32]');

-- Petigru (685) ↔ Thomas Cooper (683) — adversarial
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
VALUES (683, 685, 'ideological_conflict', '1828-01-01', '1839-05-11', 3, 'adversarial',
        (SELECT source_id FROM sources WHERE title = 'South Carolina: A History'),
        'Cooper''s decades of disunionist instruction at SC College gave the Nullifiers their intellectual cadre; Petigru''s 1832 senate bill targeted his removal on anticlerical-deism grounds. End_date = Cooper''s death. [ch.fn 27, 42]');

-- Caroline Petigru (lookup) — kinship: daughter of Petigru.
-- Petigru = 685 < new Caroline row (will be > 1256), so 685 is always the low id.
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
SELECT 685, p.person_id, 'kinship_parent_child', '1819-01-01', '1863-03-09', 3, 'aligned', 8,
       'Daughter Caroline; recipient of Petigru''s 1862 Summerville letter recounting his entry to Waddel''s academy; sent to NYC 1834 amid post-Nullification climate. [ch.fn 7, 19, 56]'
  FROM people p WHERE p.full_name = 'Caroline Petigru' AND p.person_id > 685;

-- Albert Petigru (lookup) — kinship: son of Petigru (died 1826).
INSERT OR IGNORE INTO relationships (person_low_id, person_high_id, relationship_type_code, start_date, end_date, strength, alignment_status_code, source_id, notes)
SELECT 685, p.person_id, 'kinship_parent_child', '1818-01-01', '1826-09-13', 3, 'aligned', 6,
       'Son Albert; died Sept 13, 1826 at age 8 from a fall on the stairs of the Charleston home. [ch.fn 19]'
  FROM people p WHERE p.full_name = 'Albert Petigru' AND p.person_id > 685;

-- -----------------------------------------------------------------------------
-- 9) RELATIONSHIP CHARACTERIZATIONS — issue-specific alignments at Nullification
-- -----------------------------------------------------------------------------
-- ALIGNED: Petigru-Legaré, Petigru-Huger, Petigru-Grayson, Petigru-Grimké,
-- Petigru-Poinsett, Petigru-Drayton on nullification 1830-1833.
-- ADVERSARIAL: Petigru-Calhoun, Petigru-Cooper on nullification 1830-1833.
-- STRAINED: Petigru-Hunt on nullification 1830-1833.

INSERT OR IGNORE INTO relationship_characterizations (
    relationship_id, event_id, date_start, date_end,
    issue_category_code, scale_level_code, alignment_status_code, strength,
    relchar_notes,
    claim_type_code, confidence_score, evidence_type_code, counterevidence_present,
    source_id, justification_note
)
SELECT r.relationship_id,
       (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'),
       '1830-01-01', '1833-03-15',
       'nullification', 'state', 'aligned', 3,
       'Aligned Unionist correspondence axis 1830-1833 (Petigru-Legaré); the spine of Petigru''s documented stance.',
       'observed', 3, 'direct_quote', 0, 8, 'Carson 1920. [ch.fn 40-41]'
  FROM relationships r
 WHERE r.person_low_id = 4 AND r.person_high_id = 685 AND r.relationship_type_code = 'correspondence';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1830-01-01', '1833-03-15', 'nullification', 'state', 'aligned', 3,
       'Petigru-Huger Charleston Union Party co-leadership 1830-1833. [ch.fn 36]',
       'observed', 3, 'mixed', 0, 6, 'Pease & Pease, 41-43.'
  FROM relationships r WHERE r.person_low_id = 94 AND r.person_high_id = 685 AND r.relationship_type_code = 'political_alliance';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1830-01-01', '1833-03-15', 'nullification', 'state', 'aligned', 2,
       'Petigru-Grayson aligned Unionist friendship through Nullification. [ch.fn 6]',
       'observed', 2, 'mixed', 0, 7, 'Grayson, Witness To Sorrow.'
  FROM relationships r WHERE r.person_low_id = 507 AND r.person_high_id = 685 AND r.relationship_type_code = 'friendship';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1833-01-01', '1834-10-12', 'nullification', 'state', 'aligned', 3,
       'Petigru-Grimké joint counsel in McCready v. Hunt (1834). [ch.fn 54]',
       'observed', 3, 'mixed', 0, 6, 'Pease & Pease + Ford 2021 on McCready.'
  FROM relationships r WHERE r.person_low_id = 685 AND r.person_high_id = 730 AND r.relationship_type_code = 'legal_connection';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1830-01-01', '1833-03-15', 'nullification', 'state', 'aligned', 3,
       'Petigru-Poinsett Charleston Unionist co-leaders; both struck in Oct 1832 violence. [ch.fn 48]',
       'observed', 3, 'direct_quote', 0, 8, 'Carson 1920, Petigru-Legaré Oct 1832.'
  FROM relationships r WHERE r.person_low_id = 3 AND r.person_high_id = 685 AND r.relationship_type_code = 'political_alliance';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1830-01-01', '1833-03-15', 'nullification', 'state', 'aligned', 2,
       'Petigru-Drayton aligned Charleston Unionists; both struck in Oct 1832. [ch.fn 48]',
       'observed', 2, 'mixed', 0, 8, 'Carson 1920, Petigru-Legaré Oct 1832.'
  FROM relationships r WHERE r.person_low_id = 5 AND r.person_high_id = 685 AND r.relationship_type_code = 'political_alliance';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1831-01-01', '1833-03-15', 'nullification', 'state', 'strained', 2,
       'Petigru-Hunt nominally aligned on nullification but strained by Hunt''s 1831 pro-tariff pamphlet, which Petigru blamed for Unionist setbacks. [ch.fn 38]',
       'observed', 2, 'mixed', 1, 8, 'Carson 1920, Petigru-Elliot Aug 1831.'
  FROM relationships r WHERE r.person_low_id = 685 AND r.person_high_id = 1082 AND r.relationship_type_code = 'professional';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1830-01-01', '1833-03-15', 'nullification', 'state', 'adversarial', 3,
       'Petigru-Calhoun ideological opposition during Nullification; Calhoun''s Exposition and Protest (1828) + Test Oath structurally opposite Petigru''s conditional constitutionalism. [ch.fn 29, 32]',
       'observed', 3, 'mixed', 0, 6, 'Pease & Pease + Edgar.'
  FROM relationships r WHERE r.person_low_id = 272 AND r.person_high_id = 685 AND r.relationship_type_code = 'ideological_conflict';

INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, (SELECT event_id FROM events WHERE event_name = 'Nullification Crisis'), '1830-01-01', '1834-12-31', 'nullification', 'state', 'adversarial', 3,
       'Petigru-Cooper adversarial; the 1832 senate-bill removal effort targets Cooper''s disunionist instruction at SC College. [ch.fn 42]',
       'observed', 3, 'mixed', 0, 6, 'Pease & Pease, 47-48.'
  FROM relationships r WHERE r.person_low_id = 683 AND r.person_high_id = 685 AND r.relationship_type_code = 'ideological_conflict';

-- 1860 Petigru-Perry alignment on SECESSION axis (extends slice 01's nullification relchar).
INSERT OR IGNORE INTO relationship_characterizations (relationship_id, event_id, date_start, date_end, issue_category_code, scale_level_code, alignment_status_code, strength, relchar_notes, claim_type_code, confidence_score, evidence_type_code, counterevidence_present, source_id, justification_note)
SELECT r.relationship_id, NULL, '1860-05-01', '1863-03-09', 'secession', 'state', 'aligned', 3,
       'Petigru-Perry alignment on secession axis at the May 1860 Charleston Democratic Convention; Petigru''s post-Convention letter to Perry ("contracted a disinclination to write or to speak, when truth is in question") confirms the alliance across the lowcountry/upcountry Unionist axis through Petigru''s death. [ch.fn 1]',
       'observed', 3, 'direct_quote', 0,
       (SELECT source_id FROM sources WHERE title = 'Benjamin F. Perry, South Carolina Unionist'),
       'Kibler 1946, 5-6 + Pease & Pease, 155. [ch.fn 1]'
  FROM relationships r WHERE r.person_low_id = 2 AND r.person_high_id = 685 AND r.relationship_type_code = 'political_alliance';

-- =============================================================================
COMMIT;

-- -----------------------------------------------------------------------------
-- VERIFICATION QUERIES — run manually after the slice:
-- -----------------------------------------------------------------------------
-- .headers on
-- .mode column
-- -- Petigru position arc 1826-1863:
-- SELECT position_id, issue_category_code, date_start, date_end,
--        position_label_code, stance_code, substr(position_notes,1,70) AS notes
--   FROM positions WHERE person_id = 685 ORDER BY date_start;
-- -- Petigru inner circle codings:
-- SELECT pe.full_name, p.issue_category_code, p.date_start, p.position_label_code, p.stance_code
--   FROM positions p JOIN people pe ON pe.person_id = p.person_id
--  WHERE p.person_id IN (4, 94, 507, 730, 3, 5, 1082, 683)
--    AND p.issue_category_code = 'nullification'
--  ORDER BY pe.full_name;
-- -- Relchars on nullification visible at year=1832:
-- SELECT rc.relationship_characterization_id,
--        r.person_low_id, r.person_high_id, r.relationship_type_code,
--        rc.alignment_status_code, rc.date_start, rc.date_end
--   FROM relationship_characterizations rc
--   JOIN relationships r ON r.relationship_id = rc.relationship_id
--  WHERE rc.issue_category_code = 'nullification'
--    AND (r.person_low_id = 685 OR r.person_high_id = 685)
--  ORDER BY r.person_low_id, r.person_high_id;
-- -- Secession axis at year=1860:
-- SELECT person_id, issue_category_code, date_start, date_end, stance_code, position_label_code
--   FROM positions WHERE issue_category_code = 'secession' ORDER BY person_id, date_start;
-- =============================================================================
