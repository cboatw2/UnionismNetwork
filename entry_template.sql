-- Example workflow: add one source, one person, one position claim.
-- Run in sqlite shell after loading schema and seed data.

BEGIN TRANSACTION;

-- 1) Add source
INSERT INTO sources (
    source_type_code,
    title,
    creator,
    date_created,
    archive,
    collection,
    box_folder,
    citation_full,
    notes
) VALUES (
    'letter',
    'Letter from James Louis Petigru to [Recipient]',
    'James Louis Petigru',
    '1832-11-15',
    'South Caroliniana Library',
    'Petigru Papers',
    'Box 2, Folder 4',
    'Petigru, James Louis. Letter to [Recipient], 15 Nov 1832. South Caroliniana Library.',
    'Replace placeholders with exact citation.'
);

-- 2) Add place (if missing)
INSERT OR IGNORE INTO places (
    place_name,
    place_type_code,
    region_sc_code,
    modern_state,
    notes
) VALUES (
    'Charleston',
    'town',
    'lowcountry',
    'SC',
    NULL
);

-- 3) Add person
INSERT INTO people (
    full_name,
    display_name,
    birth_year,
    race_code,
    class_code,
    occupation,
    home_region_sc_code,
    source_density_code,
    representation_depth_code,
    erasure_flag,
    notes
) VALUES (
    'James Louis Petigru',
    'James L. Petigru',
    1789,
    'white',
    'elite',
    'Lawyer',
    'lowcountry',
    'high',
    'full',
    0,
    'Seed record for dissertation coding workflow.'
);

-- Optional: add another actor to support relationship coding examples
INSERT INTO people (
    full_name,
    display_name,
    race_code,
    class_code,
    occupation,
    source_density_code,
    representation_depth_code,
    erasure_flag,
    notes
) VALUES (
    'John C. Calhoun',
    'John C. Calhoun',
    'white',
    'elite',
    'Politician',
    'high',
    'full',
    0,
    'Second actor for relationship characterization examples.'
);

-- 4) Add position claim with defensibility fields
INSERT INTO positions (
    person_id,
    event_id,
    date_start,
    date_end,
    issue_category_code,
    position_label_code,
    ideology_score,
    scale_level_code,
    region_relevance_code,
    stance_on_union,
    stance_on_states_rights,
    stance_on_slavery,
    stance_on_secession,
    claim_type_code,
    confidence_score,
    evidence_type_code,
    counterevidence_present,
    source_id,
    justification_note,
    interpretive_note
) VALUES (
    (SELECT person_id FROM people WHERE full_name = 'James Louis Petigru'),
    NULL,
    '1832-11-15',
    NULL,
    'nullification',
    'constitutional_unionist',
    -0.85,
    'national',
    'lowcountry',
    -0.95,
    -0.60,
    -0.10,
    -0.90,
    'observed',
    3,
    'direct_quote',
    0,
    (SELECT MAX(source_id) FROM sources),
    'Letter explicitly supports constitutional Union over nullification logic.',
    'Update scores only if coding rubric changes.'
);

-- 5) Add a baseline relationship tie between two actors
INSERT INTO relationships (
    person_low_id,
    person_high_id,
    relationship_type_code,
    start_date,
    strength,
    alignment_status_code,
    source_id,
    notes
) VALUES (
    (
        SELECT
            CASE
                WHEN p1.person_id < p2.person_id THEN p1.person_id
                ELSE p2.person_id
            END
        FROM people p1, people p2
        WHERE p1.full_name = 'James Louis Petigru'
          AND p2.full_name = 'John C. Calhoun'
    ),
    (
        SELECT
            CASE
                WHEN p1.person_id < p2.person_id THEN p2.person_id
                ELSE p1.person_id
            END
        FROM people p1, people p2
        WHERE p1.full_name = 'James Louis Petigru'
          AND p2.full_name = 'John C. Calhoun'
    ),
    'political_alliance',
    '1830-01-01',
    2,
    'partially_aligned',
    (SELECT MAX(source_id) FROM sources),
    'Baseline tie: relationship exists, but alignment varies by issue.'
);

-- 6) Add issue-specific relationship characterization (core nuance layer)
INSERT INTO relationship_characterizations (
    relationship_id,
    event_id,
    date_start,
    date_end,
    issue_category_code,
    scale_level_code,
    alignment_status_code,
    strength,
    claim_type_code,
    confidence_score,
    evidence_type_code,
    counterevidence_present,
    source_id,
    justification_note,
    notes
) VALUES (
    (
        SELECT relationship_id
        FROM relationships
        WHERE relationship_type_code = 'political_alliance'
        ORDER BY relationship_id DESC
        LIMIT 1
    ),
    NULL,
    '1832-11-01',
    NULL,
    'nullification',
    'state',
    'fractured',
    1,
    'observed',
    2,
    'mixed',
    0,
    (SELECT MAX(source_id) FROM sources),
    'During nullification politics, alignment weakens despite ongoing political contact.',
    'Use additional records for later issue shifts (e.g., federal power, secession).'
);

COMMIT;

-- Optional checks
SELECT person_id, full_name, class_code, source_density_code, representation_depth_code
FROM people
ORDER BY person_id DESC
LIMIT 5;

SELECT position_id, person_id, issue_category_code, position_label_code, confidence_score, source_id
FROM positions
ORDER BY position_id DESC
LIMIT 5;

SELECT
    rc.relationship_characterization_id,
    rc.relationship_id,
    rc.issue_category_code,
    rc.scale_level_code,
    rc.alignment_status_code,
    rc.strength,
    rc.confidence_score
FROM relationship_characterizations rc
ORDER BY rc.relationship_characterization_id DESC
LIMIT 5;
