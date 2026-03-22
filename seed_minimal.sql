BEGIN TRANSACTION;

INSERT OR IGNORE INTO lkp_race (race_code, label) VALUES
('white', 'White'),
('black', 'Black'),
('unknown', 'Unknown/Not yet identified');

INSERT OR IGNORE INTO lkp_class_status (class_code, label) VALUES
('elite', 'Elite'),
('non_elite', 'Non-elite'),
('unknown', 'Unknown');

INSERT OR IGNORE INTO lkp_source_type (source_type_code, label) VALUES
('letter', 'Letter'),
('newspaper', 'Newspaper'),
('legislative_record', 'Legislative record'),
('military_record', 'Military record'),
('diary', 'Diary'),
('secondary', 'Secondary source'),
('other', 'Other');

INSERT OR IGNORE INTO lkp_event_type (event_type_code, label) VALUES
('political_crisis', 'Political crisis'),
('election', 'Election'),
('military_event', 'Military event'),
('party_realignment', 'Party realignment'),
('publication', 'Publication'),
('other', 'Other');

INSERT OR IGNORE INTO lkp_relationship_type (relationship_type_code, label) VALUES
('kinship', 'Kinship'),
('friendship', 'Friendship'),
('political_alliance', 'Political alliance'),
('correspondence', 'Correspondence'),
('legal_connection', 'Legal connection'),
('ideological_conflict', 'Ideological conflict'),
('other', 'Other');

INSERT OR IGNORE INTO lkp_alignment_status (alignment_status_code, label) VALUES
('aligned', 'Aligned'),
('partially_aligned', 'Partially aligned'),
('strained', 'Strained'),
('fractured', 'Fractured'),
('adversarial', 'Adversarial');

INSERT OR IGNORE INTO lkp_issue_category (issue_category_code, label) VALUES
('nullification', 'Nullification'),
('secession', 'Secession'),
('slavery', 'Slavery'),
('federal_power', 'Federal power'),
('party_affiliation', 'Party affiliation'),
('other', 'Other');

INSERT OR IGNORE INTO lkp_position_label (position_label_code, label) VALUES
('constitutional_unionist', 'Constitutional Unionist'),
('conditional_unionist', 'Conditional Unionist'),
('states_rights_unionist', 'States rights Unionist'),
('pro_slavery_unionist', 'Pro-slavery Unionist'),
('mixed_alignment', 'Mixed alignment'),
('unknown', 'Unknown/Unclear');

INSERT OR IGNORE INTO lkp_scale_level (scale_level_code, label) VALUES
('local', 'Local'),
('state', 'State'),
('regional', 'Regional'),
('national', 'National'),
('international', 'International');

INSERT OR IGNORE INTO lkp_confidence_score (confidence_score, label) VALUES
(1, 'Low confidence'),
(2, 'Moderate confidence'),
(3, 'High confidence');

INSERT OR IGNORE INTO lkp_evidence_type (evidence_type_code, label) VALUES
('direct_quote', 'Direct quote/source statement'),
('inferred', 'Inferred from context'),
('indirect_reference', 'Indirect reference'),
('mixed', 'Mixed evidence');

INSERT OR IGNORE INTO lkp_claim_type (claim_type_code, label) VALUES
('observed', 'Observed'),
('inferred', 'Inferred'),
('contested', 'Contested');

INSERT OR IGNORE INTO lkp_representation_depth (representation_depth_code, label) VALUES
('full', 'Full'),
('partial', 'Partial'),
('fragmentary', 'Fragmentary');

INSERT OR IGNORE INTO lkp_source_density (source_density_code, label) VALUES
('high', 'High'),
('medium', 'Medium'),
('low', 'Low');

INSERT OR IGNORE INTO lkp_erasure_reason (erasure_reason_code, label) VALUES
('archival_loss', 'Archival loss'),
('biased_records', 'Biased source survival'),
('indirect_only', 'Only indirect mention'),
('unknown', 'Unknown');

INSERT OR IGNORE INTO lkp_residence_type (residence_type_code, label) VALUES
('birth', 'Birth place'),
('household', 'Household residence'),
('professional_base', 'Professional base'),
('temporary_residence', 'Temporary residence'),
('exile', 'Exile/refuge');

INSERT OR IGNORE INTO lkp_org_type (org_type_code, label) VALUES
('party', 'Political party'),
('newspaper', 'Newspaper'),
('military_unit', 'Military unit'),
('church', 'Church'),
('association', 'Association'),
('other', 'Other');

INSERT OR IGNORE INTO lkp_place_type (place_type_code, label) VALUES
('town', 'Town/City'),
('county', 'County/District'),
('state', 'State'),
('region', 'Region'),
('nation', 'Nation'),
('other', 'Other');

INSERT OR IGNORE INTO lkp_region_sc (region_sc_code, label) VALUES
('upcountry', 'Upcountry/Backcountry'),
('lowcountry', 'Lowcountry'),
('midlands', 'Midlands'),
('outside_sc', 'Outside South Carolina');

COMMIT;
