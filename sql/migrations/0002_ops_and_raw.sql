-- Migration 0002: ops + raw core tables

CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    version       TEXT PRIMARY KEY,
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum      TEXT,
    description   TEXT
);

CREATE TABLE IF NOT EXISTS ops.ingestion_batches (
    batch_id            UUID PRIMARY KEY,
    source_track        TEXT NOT NULL,
    object_path         TEXT NOT NULL,
    object_version      TEXT,
    content_sha256      TEXT NOT NULL,
    logical_cutoff      TIMESTAMP,
    state               TEXT NOT NULL,
    row_count           BIGINT,
    accepted_count      BIGINT,
    quarantined_count   BIGINT,
    error_summary       TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ingestion_batches_state_chk CHECK (
        state IN (
            'discovered',
            'loading',
            'loaded',
            'validating',
            'transformed',
            'exported',
            'failed',
            'skipped_no_new_data'
        )
    ),
    CONSTRAINT ingestion_batches_track_chk CHECK (
        source_track IN (
            'public_historical',
            'historical_replay',
            'synthetic_quality',
            'synthetic_campus'
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_ingestion_batches_checksum
    ON ops.ingestion_batches (content_sha256);

CREATE INDEX IF NOT EXISTS ix_ingestion_batches_track_state
    ON ops.ingestion_batches (source_track, state);

-- One source row per batch + file position; business fields as text.
CREATE TABLE IF NOT EXISTS raw.incident_rows (
    batch_id            UUID NOT NULL REFERENCES ops.ingestion_batches (batch_id),
    file_row_number     BIGINT NOT NULL,
    content_fingerprint TEXT NOT NULL,
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    number              TEXT,
    incident_state      TEXT,
    active              TEXT,
    reassignment_count  TEXT,
    reopen_count        TEXT,
    sys_mod_count       TEXT,
    made_sla            TEXT,
    caller_id           TEXT,
    opened_by           TEXT,
    opened_at           TEXT,
    sys_created_by      TEXT,
    sys_created_at      TEXT,
    sys_updated_by      TEXT,
    sys_updated_at      TEXT,
    contact_type        TEXT,
    location            TEXT,
    category            TEXT,
    subcategory         TEXT,
    u_symptom           TEXT,
    cmdb_ci             TEXT,
    impact              TEXT,
    urgency             TEXT,
    priority            TEXT,
    assignment_group    TEXT,
    assigned_to         TEXT,
    knowledge           TEXT,
    u_priority_confirmation TEXT,
    notify              TEXT,
    problem_id          TEXT,
    rfc                 TEXT,
    vendor              TEXT,
    caused_by           TEXT,
    closed_code         TEXT,
    resolved_by         TEXT,
    resolved_at         TEXT,
    closed_at           TEXT,
    PRIMARY KEY (batch_id, file_row_number)
);

CREATE INDEX IF NOT EXISTS ix_raw_incident_number
    ON raw.incident_rows (number);
