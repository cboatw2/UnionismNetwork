-- seed_mvp_demo.sql
-- Demo-only starter rows so the interactive app has nodes/places immediately.
-- IMPORTANT: These are placeholders for prototyping only. Replace with your own sourced claims.

BEGIN TRANSACTION;

-- A placeholder source for demo relationships/events.
INSERT INTO sources (
  source_type_code,
  title,
  creator,
  date_created,
  citation_full,
  notes
) VALUES (
  'secondary',
  'MVP demo seed (placeholder citations)',
  'UnionismNetwork scaffold',
  '2026-04-29',
  'Placeholder citation for MVP scaffolding only. Replace with archival/primary citations before analysis.',
  'Do not treat this row as evidence; it only prevents NULL source references in demo data.'
);

-- Minimal place hierarchy
INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, modern_state, notes)
VALUES ('United States', 'nation', NULL, 39.8283, -98.5795, NULL, 'Nation (approx center)');

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, modern_state, notes)
VALUES ('Mexico', 'nation', NULL, 23.6345, -102.5528, NULL, 'Nation (approx center)');

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, modern_state, notes)
VALUES ('Europe', 'region', NULL, 54.5260, 15.2551, NULL, 'Region (approx center)');

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, modern_state, notes)
VALUES (
  'South Carolina',
  'state',
  (SELECT place_id FROM places WHERE place_name = 'United States' AND place_type_code = 'nation'),
  33.8361,
  -81.1637,
  'SC',
  'State (approx center)'
);

-- Must-have cities
INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, region_sc_code, modern_state)
VALUES (
  'Charleston',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'South Carolina' AND place_type_code = 'state'),
  32.7765,
  -79.9311,
  'lowcountry',
  'SC'
);

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, region_sc_code, modern_state)
VALUES (
  'Columbia',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'South Carolina' AND place_type_code = 'state'),
  34.0007,
  -81.0348,
  'midlands',
  'SC'
);

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, region_sc_code, modern_state)
VALUES (
  'Greenville',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'South Carolina' AND place_type_code = 'state'),
  34.8526,
  -82.3940,
  'upcountry',
  'SC'
);

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, region_sc_code, modern_state)
VALUES (
  'Abbeville',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'South Carolina' AND place_type_code = 'state'),
  34.1782,
  -82.3790,
  'upcountry',
  'SC'
);

INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, region_sc_code, modern_state)
VALUES (
  'Pendleton',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'South Carolina' AND place_type_code = 'state'),
  34.6518,
  -82.7840,
  'upcountry',
  'SC'
);

-- Washington, D.C.
INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, modern_state, notes)
VALUES (
  'Washington',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'United States' AND place_type_code = 'nation'),
  38.9072,
  -77.0369,
  'DC',
  'Washington, D.C.'
);

-- Mexico City
INSERT OR IGNORE INTO places (place_name, place_type_code, parent_place_id, latitude, longitude, modern_state, notes)
VALUES (
  'Mexico City',
  'town',
  (SELECT place_id FROM places WHERE place_name = 'Mexico' AND place_type_code = 'nation'),
  19.4326,
  -99.1332,
  NULL,
  'Ciudad de México'
);

-- People (Phase 1 roster)
INSERT OR IGNORE INTO people (
  full_name,
  display_name,
  race_code,
  class_code,
  occupation,
  home_region_sc_code,
  source_density_code,
  representation_depth_code,
  erasure_flag,
  notes
) VALUES
('James Louis Petigru', 'James L. Petigru', 'white', 'elite', 'Lawyer', 'lowcountry', 'high', 'full', 0, 'MVP roster (demo seed). Replace with sourced notes.'),
('Benjamin Franklin Perry', 'B. F. Perry', 'white', 'elite', 'Lawyer / Editor', 'upcountry', 'high', 'full', 0, 'MVP roster (demo seed). Replace with sourced notes.'),
('Joel Roberts Poinsett', 'Joel R. Poinsett', 'white', 'elite', 'Politician / Diplomat', 'lowcountry', 'high', 'full', 0, 'MVP roster (demo seed). Replace with sourced notes.'),
('Hugh Legaré', 'Hugh Legaré', 'white', 'elite', 'Politician', 'lowcountry', 'medium', 'partial', 0, 'MVP roster (demo seed). Replace with sourced notes.'),
('William Drayton', 'William Drayton', 'white', 'elite', 'Politician', 'lowcountry', 'medium', 'partial', 0, 'MVP roster (demo seed). Replace with sourced notes.'),
('William Elliott', 'William Elliott', 'white', 'elite', 'Politician', 'lowcountry', 'medium', 'partial', 0, 'MVP roster (demo seed). Replace with sourced notes.'),
('Edward McCrady', 'Edward McCrady', 'white', 'elite', 'Historian / Lawyer', 'lowcountry', 'low', 'fragmentary', 0, 'MVP roster (demo seed). Replace with sourced notes.');

-- Simple residence anchors so points appear on the map (demo-only; replace with sourced dates).
INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT p.person_id, pl.place_id, 'professional_base', '1830-01-01', NULL, (SELECT MAX(source_id) FROM sources), 'Demo-only map anchor.'
FROM people p
JOIN places pl ON pl.place_name = 'Charleston' AND pl.place_type_code = 'town'
WHERE p.full_name IN ('James Louis Petigru', 'Joel Roberts Poinsett', 'Hugh Legaré', 'William Drayton', 'William Elliott');

INSERT INTO person_place_residence (person_id, place_id, residence_type_code, date_start, date_end, source_id, notes)
SELECT p.person_id, pl.place_id, 'professional_base', '1830-01-01', NULL, (SELECT MAX(source_id) FROM sources), 'Demo-only map anchor.'
FROM people p
JOIN places pl ON pl.place_name = 'Greenville' AND pl.place_type_code = 'town'
WHERE p.full_name IN ('Benjamin Franklin Perry');

-- A few anchor events (minimal; replace descriptions/citations as you build).
INSERT INTO events (event_name, event_type_code, start_date, end_date, place_id, description)
VALUES
('Missouri Compromise', 'other', '1820-03-03', NULL, NULL, 'Anchor event (demo).'),
('Tariff of 1828', 'other', '1828-05-19', NULL, NULL, 'Anchor event (demo).'),
('Nullification Crisis', 'political_crisis', '1832-11-01', '1833-03-01', (SELECT place_id FROM places WHERE place_name = 'South Carolina' AND place_type_code = 'state'), 'Anchor event window (demo).');

COMMIT;
