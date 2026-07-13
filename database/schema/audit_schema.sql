CREATE SCHEMA IF NOT EXISTS audit;
 
CREATE TABLE audit.query_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    generated_sql TEXT, -- NULL if generation itself failed
    context_tables TEXT[], -- what the context builder selected
 
    -- versioning info
    model_version VARCHAR(50), -- model string 'gpt-4o-mini-2024-07-18'
    prompt_version VARCHAR(64), -- prompt template
    contract_version VARCHAR(64), -- runtime_contract.yaml
    metadata_version VARCHAR(64), -- last scan's map state
 
    -- failure handling
    failure_type VARCHAR(20) NOT NULL DEFAULT 'none'
                CHECK (failure_type IN ('hard_fail','soft_fail','none')),
    failing_check VARCHAR(50), -- e.g. 'restricted_column', 'missing_limit'
    failure_reason TEXT,
    action_taken VARCHAR(30) NOT NULL DEFAULT 'allow'
                CHECK (action_taken IN ('allow','allow_and_log','rewrite','block')),
    rewrite_detail TEXT, -- e.g. 'appended LIMIT 1000'
 
    -- PII and results
    pii_columns_masked TEXT[],
    result_row_count INTEGER,
    execution_time_ms INTEGER,
    queried_at TIMESTAMP NOT NULL DEFAULT NOW(),
 
    -- a hard fail must name its check; a rewrite must say what it did
    CONSTRAINT chk_failure_has_check
        CHECK (failure_type = 'none' OR failing_check IS NOT NULL),
    CONSTRAINT chk_rewrite_has_detail
        CHECK (action_taken <> 'rewrite' OR rewrite_detail IS NOT NULL)
);
