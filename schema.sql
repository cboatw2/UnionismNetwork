PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Lookup tables keep coding consistent as the project grows.
CREATE TABLE IF NOT EXISTS lkp_race (
	race_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_class_status (
	class_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_source_type (
	source_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_event_type (
	event_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_relationship_type (
	relationship_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_alignment_status (
	alignment_status_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_issue_category (
	issue_category_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_position_label (
	position_label_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_scale_level (
	scale_level_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_confidence_score (
	confidence_score INTEGER PRIMARY KEY,
	label TEXT NOT NULL UNIQUE,
	CHECK (confidence_score BETWEEN 1 AND 3)
);

CREATE TABLE IF NOT EXISTS lkp_evidence_type (
	evidence_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_claim_type (
	claim_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_representation_depth (
	representation_depth_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_source_density (
	source_density_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_erasure_reason (
	erasure_reason_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_residence_type (
	residence_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_org_type (
	org_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_place_type (
	place_type_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS lkp_region_sc (
	region_sc_code TEXT PRIMARY KEY,
	label TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS places (
	place_id INTEGER PRIMARY KEY,
	place_name TEXT NOT NULL,
	place_type_code TEXT NOT NULL REFERENCES lkp_place_type(place_type_code),
	parent_place_id INTEGER REFERENCES places(place_id),
	latitude REAL,
	longitude REAL,
	region_sc_code TEXT REFERENCES lkp_region_sc(region_sc_code),
	modern_state TEXT,
	notes TEXT,
	UNIQUE (place_name, place_type_code, parent_place_id)
);

CREATE TABLE IF NOT EXISTS people (
	person_id INTEGER PRIMARY KEY,
	full_name TEXT,
	display_name TEXT,
	birth_year INTEGER,
	death_year INTEGER,
	birth_place_id INTEGER REFERENCES places(place_id),
	death_place_id INTEGER REFERENCES places(place_id),
	race_code TEXT REFERENCES lkp_race(race_code),
	gender TEXT,
	class_code TEXT REFERENCES lkp_class_status(class_code),
	occupation TEXT,
	home_region_sc_code TEXT REFERENCES lkp_region_sc(region_sc_code),
	enslaved_status TEXT,
	source_density_code TEXT REFERENCES lkp_source_density(source_density_code),
	representation_depth_code TEXT REFERENCES lkp_representation_depth(representation_depth_code),
	erasure_flag INTEGER NOT NULL DEFAULT 0 CHECK (erasure_flag IN (0, 1)),
	erasure_reason_code TEXT REFERENCES lkp_erasure_reason(erasure_reason_code),
	notes TEXT,
	created_at TEXT NOT NULL DEFAULT (datetime('now')),
	updated_at TEXT NOT NULL DEFAULT (datetime('now')),
	CHECK (birth_year IS NULL OR birth_year BETWEEN 1500 AND 2100),
	CHECK (death_year IS NULL OR death_year BETWEEN 1500 AND 2100),
	CHECK (death_year IS NULL OR birth_year IS NULL OR death_year >= birth_year),
	CHECK (erasure_flag = 1 OR erasure_reason_code IS NULL)
);

CREATE TABLE IF NOT EXISTS person_aliases (
	alias_id INTEGER PRIMARY KEY,
	person_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
	alias_name TEXT NOT NULL,
	source_id INTEGER REFERENCES sources(source_id),
	notes TEXT,
	UNIQUE (person_id, alias_name)
);

CREATE TABLE IF NOT EXISTS sources (
	source_id INTEGER PRIMARY KEY,
	source_type_code TEXT NOT NULL REFERENCES lkp_source_type(source_type_code),
	title TEXT NOT NULL,
	creator TEXT,
	date_created TEXT,
	archive TEXT,
	collection TEXT,
	box_folder TEXT,
	url TEXT,
	citation_full TEXT,
	notes TEXT,
	created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
	event_id INTEGER PRIMARY KEY,
	event_name TEXT NOT NULL,
	event_type_code TEXT NOT NULL REFERENCES lkp_event_type(event_type_code),
	start_date TEXT,
	end_date TEXT,
	place_id INTEGER REFERENCES places(place_id),
	description TEXT,
	CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS organizations (
	organization_id INTEGER PRIMARY KEY,
	name TEXT NOT NULL UNIQUE,
	org_type_code TEXT REFERENCES lkp_org_type(org_type_code),
	place_id INTEGER REFERENCES places(place_id),
	start_date TEXT,
	end_date TEXT,
	notes TEXT,
	CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS person_organization (
	person_org_id INTEGER PRIMARY KEY,
	person_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
	organization_id INTEGER NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
	role TEXT,
	date_start TEXT,
	date_end TEXT,
	source_id INTEGER REFERENCES sources(source_id),
	notes TEXT,
	CHECK (date_end IS NULL OR date_start IS NULL OR date_end >= date_start)
);

CREATE TABLE IF NOT EXISTS person_place_residence (
	residence_id INTEGER PRIMARY KEY,
	person_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
	place_id INTEGER NOT NULL REFERENCES places(place_id),
	residence_type_code TEXT REFERENCES lkp_residence_type(residence_type_code),
	date_start TEXT,
	date_end TEXT,
	source_id INTEGER REFERENCES sources(source_id),
	notes TEXT,
	CHECK (date_end IS NULL OR date_start IS NULL OR date_end >= date_start)
);

CREATE TABLE IF NOT EXISTS relationships (
	relationship_id INTEGER PRIMARY KEY,
	person_low_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
	person_high_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
	relationship_type_code TEXT NOT NULL REFERENCES lkp_relationship_type(relationship_type_code),
	start_date TEXT,
	end_date TEXT,
	strength INTEGER CHECK (strength BETWEEN 1 AND 3),
	alignment_status_code TEXT REFERENCES lkp_alignment_status(alignment_status_code),
	source_id INTEGER REFERENCES sources(source_id),
	notes TEXT,
	CHECK (person_low_id < person_high_id),
	CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
	UNIQUE (person_low_id, person_high_id, relationship_type_code, start_date)
);

-- Issue-specific relationship characterizations capture fluctuation by topic and scale.
CREATE TABLE IF NOT EXISTS relationship_characterizations (
	relationship_characterization_id INTEGER PRIMARY KEY,
	relationship_id INTEGER NOT NULL REFERENCES relationships(relationship_id) ON DELETE CASCADE,
	event_id INTEGER REFERENCES events(event_id),
	date_start TEXT,
	date_end TEXT,
	issue_category_code TEXT NOT NULL REFERENCES lkp_issue_category(issue_category_code),
	scale_level_code TEXT REFERENCES lkp_scale_level(scale_level_code),
	alignment_status_code TEXT NOT NULL REFERENCES lkp_alignment_status(alignment_status_code),
	strength INTEGER CHECK (strength BETWEEN 1 AND 3),
	claim_type_code TEXT NOT NULL REFERENCES lkp_claim_type(claim_type_code),
	confidence_score INTEGER NOT NULL REFERENCES lkp_confidence_score(confidence_score),
	evidence_type_code TEXT NOT NULL REFERENCES lkp_evidence_type(evidence_type_code),
	counterevidence_present INTEGER NOT NULL DEFAULT 0 CHECK (counterevidence_present IN (0, 1)),
	source_id INTEGER NOT NULL REFERENCES sources(source_id),
	justification_note TEXT NOT NULL,
	notes TEXT,
	CHECK (date_end IS NULL OR date_start IS NULL OR date_end >= date_start),
	UNIQUE (relationship_id, issue_category_code, date_start, source_id)
);

CREATE TABLE IF NOT EXISTS positions (
	position_id INTEGER PRIMARY KEY,
	person_id INTEGER NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
	event_id INTEGER REFERENCES events(event_id),
	date_start TEXT,
	date_end TEXT,
	issue_category_code TEXT NOT NULL REFERENCES lkp_issue_category(issue_category_code),
	position_label_code TEXT NOT NULL REFERENCES lkp_position_label(position_label_code),
	ideology_score REAL CHECK (ideology_score >= -1.0 AND ideology_score <= 1.0),
	scale_level_code TEXT NOT NULL REFERENCES lkp_scale_level(scale_level_code),
	region_relevance_code TEXT REFERENCES lkp_region_sc(region_sc_code),
	stance_on_union REAL CHECK (stance_on_union >= -1.0 AND stance_on_union <= 1.0),
	stance_on_states_rights REAL CHECK (stance_on_states_rights >= -1.0 AND stance_on_states_rights <= 1.0),
	stance_on_slavery REAL CHECK (stance_on_slavery >= -1.0 AND stance_on_slavery <= 1.0),
	stance_on_secession REAL CHECK (stance_on_secession >= -1.0 AND stance_on_secession <= 1.0),
	claim_type_code TEXT NOT NULL REFERENCES lkp_claim_type(claim_type_code),
	confidence_score INTEGER NOT NULL REFERENCES lkp_confidence_score(confidence_score),
	evidence_type_code TEXT NOT NULL REFERENCES lkp_evidence_type(evidence_type_code),
	counterevidence_present INTEGER NOT NULL DEFAULT 0 CHECK (counterevidence_present IN (0, 1)),
	source_id INTEGER NOT NULL REFERENCES sources(source_id),
	justification_note TEXT NOT NULL,
	interpretive_note TEXT,
	CHECK (date_end IS NULL OR date_start IS NULL OR date_end >= date_start)
);

CREATE TABLE IF NOT EXISTS correspondence (
	letter_id INTEGER PRIMARY KEY,
	source_id INTEGER NOT NULL UNIQUE REFERENCES sources(source_id) ON DELETE CASCADE,
	sender_id INTEGER REFERENCES people(person_id),
	recipient_id INTEGER REFERENCES people(person_id),
	date_sent TEXT,
	origin_place_id INTEGER REFERENCES places(place_id),
	destination_place_id INTEGER REFERENCES places(place_id),
	summary TEXT,
	topics TEXT,
	tone TEXT,
	network_significance INTEGER CHECK (network_significance BETWEEN 1 AND 3)
);

CREATE INDEX IF NOT EXISTS idx_people_name ON people(full_name);
CREATE INDEX IF NOT EXISTS idx_people_class_code ON people(class_code);
CREATE INDEX IF NOT EXISTS idx_people_region ON people(home_region_sc_code);

CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type_code);
CREATE INDEX IF NOT EXISTS idx_sources_date ON sources(date_created);

CREATE INDEX IF NOT EXISTS idx_events_start_date ON events(start_date);

CREATE INDEX IF NOT EXISTS idx_relationships_pair ON relationships(person_low_id, person_high_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_dates ON relationships(start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_relchar_relationship ON relationship_characterizations(relationship_id);
CREATE INDEX IF NOT EXISTS idx_relchar_issue ON relationship_characterizations(issue_category_code);
CREATE INDEX IF NOT EXISTS idx_relchar_scale ON relationship_characterizations(scale_level_code);
CREATE INDEX IF NOT EXISTS idx_relchar_dates ON relationship_characterizations(date_start, date_end);

CREATE INDEX IF NOT EXISTS idx_positions_person ON positions(person_id);
CREATE INDEX IF NOT EXISTS idx_positions_issue ON positions(issue_category_code);
CREATE INDEX IF NOT EXISTS idx_positions_dates ON positions(date_start, date_end);
CREATE INDEX IF NOT EXISTS idx_positions_confidence ON positions(confidence_score);

-- Composite indexes that match the API's most common filtering patterns.
CREATE INDEX IF NOT EXISTS idx_positions_person_issue_dates
	ON positions(person_id, issue_category_code, date_start, date_end);

CREATE INDEX IF NOT EXISTS idx_relchar_rel_issue_scale_dates
	ON relationship_characterizations(relationship_id, issue_category_code, scale_level_code, date_start, date_end);

CREATE INDEX IF NOT EXISTS idx_residence_person_dates
	ON person_place_residence(person_id, date_start, date_end);

CREATE INDEX IF NOT EXISTS idx_relationships_type_dates
	ON relationships(relationship_type_code, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_people_display_name ON people(display_name);
CREATE INDEX IF NOT EXISTS idx_places_parent ON places(parent_place_id);

CREATE INDEX IF NOT EXISTS idx_residence_person ON person_place_residence(person_id);
CREATE INDEX IF NOT EXISTS idx_residence_place ON person_place_residence(place_id);

CREATE INDEX IF NOT EXISTS idx_correspondence_date ON correspondence(date_sent);
CREATE INDEX IF NOT EXISTS idx_correspondence_sender ON correspondence(sender_id);
CREATE INDEX IF NOT EXISTS idx_correspondence_recipient ON correspondence(recipient_id);

CREATE TRIGGER IF NOT EXISTS trg_people_updated_at
AFTER UPDATE ON people
FOR EACH ROW
BEGIN
	UPDATE people
	SET updated_at = datetime('now')
	WHERE person_id = OLD.person_id;
END;

COMMIT;
