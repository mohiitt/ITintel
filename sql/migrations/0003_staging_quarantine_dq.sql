-- Migration 0003: staging, quarantine, and DQ operational tables

CREATE TABLE IF NOT EXISTS staging.incident_events (
    event_id            BIGSERIAL PRIMARY KEY,
    source_track        TEXT NOT NULL,
    batch_id            UUID NOT NULL REFERENCES ops.ingestion_batches (batch_id),
    file_row_number     BIGINT NOT NULL,
    incident_number     TEXT NOT NULL,
    incident_state      TEXT,
    active              BOOLEAN,
    reassignment_count  INTEGER,
    reopen_count        INTEGER,
    sys_mod_count       INTEGER,
    made_sla            BOOLEAN,
    opened_at           TIMESTAMP,
    sys_created_at      TIMESTAMP,
    sys_updated_at      TIMESTAMP,
    resolved_at         TIMESTAMP,
    closed_at           TIMESTAMP,
    contact_type        TEXT,
    category            TEXT,
    subcategory         TEXT,
    impact              TEXT,
    urgency             TEXT,
    priority            TEXT,
    assignment_group    TEXT,
    assigned_to         TEXT,
    closed_code         TEXT,
    resolved_by         TEXT,
    event_identity_key  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT staging_events_track_chk CHECK (
        source_track IN (
            'public_historical',
            'historical_replay',
            'synthetic_quality',
            'synthetic_campus'
        )
    ),
    UNIQUE (source_track, batch_id, file_row_number)
);

CREATE INDEX IF NOT EXISTS ix_staging_events_incident
    ON staging.incident_events (source_track, incident_number, sys_updated_at);

CREATE TABLE IF NOT EXISTS quarantine.incident_rows (
    quarantine_id       BIGSERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL REFERENCES ops.ingestion_batches (batch_id),
    file_row_number     BIGINT NOT NULL,
    primary_rule_id     TEXT NOT NULL,
    disposition         TEXT NOT NULL DEFAULT 'quarantined',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, file_row_number)
);

CREATE TABLE IF NOT EXISTS quarantine.row_violations (
    violation_id        BIGSERIAL PRIMARY KEY,
    quarantine_id       BIGINT NOT NULL REFERENCES quarantine.incident_rows (quarantine_id),
    rule_id             TEXT NOT NULL,
    rule_version        TEXT NOT NULL,
    severity            TEXT NOT NULL,
    field_name          TEXT,
    explanation         TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.dq_runs (
    dq_run_id           UUID PRIMARY KEY,
    batch_id            UUID NOT NULL REFERENCES ops.ingestion_batches (batch_id),
    source_track        TEXT NOT NULL,
    status              TEXT NOT NULL,
    rows_checked        BIGINT,
    rows_accepted       BIGINT,
    rows_quarantined    BIGINT,
    rows_excluded_dup   BIGINT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.dq_check_results (
    check_result_id     BIGSERIAL PRIMARY KEY,
    dq_run_id           UUID NOT NULL REFERENCES ops.dq_runs (dq_run_id),
    rule_id             TEXT NOT NULL,
    rule_version        TEXT NOT NULL,
    scope               TEXT,
    status              TEXT NOT NULL,
    rows_checked        BIGINT,
    failure_count       BIGINT,
    distinct_affected   BIGINT,
    threshold           NUMERIC,
    details             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.row_quality_issues (
    issue_id            BIGSERIAL PRIMARY KEY,
    batch_id            UUID NOT NULL REFERENCES ops.ingestion_batches (batch_id),
    file_row_number     BIGINT NOT NULL,
    rule_id             TEXT NOT NULL,
    rule_version        TEXT NOT NULL,
    severity            TEXT NOT NULL,
    field_name          TEXT,
    explanation         TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
