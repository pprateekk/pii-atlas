CREATE SCHEMA IF NOT EXISTS atlas;

-- one row per connected system (postgres for now, gdrive later)
CREATE TABLE atlas.source_systems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    kind VARCHAR(20) NOT NULL CHECK (kind IN ('postgres', 'gdrive')),
    display_name TEXT NOT NULL,
    connection_ref TEXT NOT NULL,
    last_scan_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
           CHECK (status IN ('active','paused', 'error'))
);

-- a table (postgres) or a file (gdrive) that is being tracked for PII
CREATE TABLE atlas.data_stores(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    system_id UUID NOT NULL REFERENCES atlas.source_systems(id) ON DELETE CASCADE,
    kind VARCHAR(10) NOT NULL CHECK (kind IN ('table','file')),
    path TEXT NOT NULL,   -- 'maplecrm.customers' or Drive path
    row_or_size_estimate BIGINT,
    sharing_scope VARCHAR(10) CHECK (sharing_scope IN ('private','domain','public')),
    owner TEXT,
    first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (system_id, path)
);

-- one row per col 
CREATE TABLE atlas.data_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    store_id UUID NOT NULL REFERENCES atlas.data_stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    declared_type TEXT NOT NULL,
    row_count BIGINT,
    null_ratio NUMERIC(5,4) CHECK (null_ratio BETWEEN 0 AND 1),
    distinct_ratio NUMERIC(5,4) CHECK (distinct_ratio BETWEEN 0 AND 1),
    min_val TEXT,
    max_val TEXT,
    avg_val NUMERIC,
    top_values JSONB,
    UNIQUE (store_id, name)
);

CREATE TABLE atlas.pi_type_registry (
    code VARCHAR(30) PRIMARY KEY,
    label TEXT NOT NULL,
    law_refs TEXT[] NOT NULL DEFAULT '{}',
    base_sensitivity VARCHAR(10) NOT NULL DEFAULT 'normal'
                    CHECK (base_sensitivity IN ('normal','sensitive','minors')),
    masking_rule VARCHAR(30) NOT NULL DEFAULT 'full_mask'
);

INSERT INTO atlas.pi_type_registry (code, label, law_refs, base_sensitivity, masking_rule) VALUES
  ('email',            'Email address',              '{PIPEDA-4.7,Law25-s.12}', 'normal',    'email_mask'),      -- p*****@domain.com
  ('person_name',      'Person name',                '{PIPEDA-4.7,Law25-s.12}', 'normal',    'initials_only'),
  ('phone',            'Phone number',               '{PIPEDA-4.7,Law25-s.12}', 'normal',    'phone_last4'),     -- (***) ***-1234
  ('street_address',   'Street / home address',      '{PIPEDA-4.7,Law25-s.12}', 'normal',    'full_mask'),
  ('dob',              'Date of birth',              '{PIPEDA-4.7,Law25-s.12}', 'normal',    'year_only'),
  ('sin',              'Social Insurance Number',    '{PIPEDA-4.7,Law25-s.12}', 'sensitive', 'sin_last3'),       -- ***-***-123
  ('ip_address',       'IP address',                 '{PIPEDA-4.7}',            'normal',    'ip_truncate'),     -- 192.168.x.x
  ('payment_token',    'Payment token',              '{PIPEDA-4.7,PCI-DSS}',    'sensitive', 'full_mask'),
  ('card_partial',     'Partial card number',        '{PCI-DSS}',               'normal',    'none'),            -- already last4
  ('credentials',      'Credentials / secrets',      '{PIPEDA-4.7}',            'sensitive', 'full_mask'),
  ('geolocation',      'Geolocation',                '{PIPEDA-4.7,Law25-s.12}', 'normal',    'full_mask'),
  ('minors_indicator', 'Data indicating a minor',    '{Law25-s.12,PIPEDA-4.7}', 'minors',    'full_mask');

-- one row per field, label
CREATE TABLE atlas.pi_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    field_id UUID NOT NULL REFERENCES atlas.data_fields(id) ON DELETE CASCADE,
    pi_type VARCHAR(30) NOT NULL REFERENCES atlas.pi_type_registry(code),
    method VARCHAR(10) NOT NULL CHECK (method IN ('pattern','llm','both')),
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    sensitivity VARCHAR(10) NOT NULL DEFAULT 'normal'
            CHECK (sensitivity IN ('normal','sensitive','minors')),
    evidence_note  TEXT NOT NULL,   -- "87% of 100 samples matched email regex"
    classified_at TIMESTAMP NOT NULL DEFAULT NOW(),
    model_version VARCHAR(50), -- NULL for pattern-only labels
    UNIQUE (field_id, pi_type)
);

-- business vocab for NL-query
CREATE TABLE atlas.glossary (
    term TEXT PRIMARY KEY,
    definition TEXT NOT NULL,
    maps_to TEXT NOT NULL   -- SQL fragment or column reference
);
 
-- specigfic to MapleCRM for now
INSERT INTO atlas.glossary (term, definition, maps_to) VALUES
  ('churned customer',  'A customer with no payment in the last 90 days',
   'customer_id NOT IN (SELECT customer_id FROM maplecrm.payments WHERE paid_at > NOW() - INTERVAL ''90 days'')'),
  ('flagged payment',   'A payment marked as suspected fraud',
   'maplecrm.payments.fraud_flag = TRUE'),
  ('last month',        'The previous full calendar month',
   'date_trunc(''month'', NOW()) - INTERVAL ''1 month'' <= paid_at AND paid_at < date_trunc(''month'', NOW())'),
  ('sensitive PII',     'Fields classified with sensitivity of sensitive or minors',
   'atlas.pi_classifications.sensitivity IN (''sensitive'',''minors'')');
 
-- findings — rule-based flags raised over the map - things that need attention
CREATE TABLE atlas.findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    rule_code VARCHAR(50) NOT NULL,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('low','medium','high')),
    field_id UUID REFERENCES atlas.data_fields(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP
);
 
-- one row per scan, pattern vs LLM cost lives here,
-- and each finished run's map-state hash becomes metadata_version
CREATE TABLE atlas.scan_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    system_id UUID NOT NULL REFERENCES atlas.source_systems(id) ON DELETE CASCADE,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    stores_seen INTEGER,
    fields_classified INTEGER,
    pattern_resolved INTEGER,          -- fields resolved with NO LLM call
    llm_resolved INTEGER,
    llm_tokens_used BIGINT,
    est_cost_usd NUMERIC(10,6),
    metadata_version VARCHAR(64)       -- SHA256 of map state at run end
);
