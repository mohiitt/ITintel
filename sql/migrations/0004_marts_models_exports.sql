-- Migration 0004: marts, models, and export release tables (shells for later phases)

CREATE TABLE IF NOT EXISTS marts.fact_tickets (
    source_track            TEXT NOT NULL,
    incident_number         TEXT NOT NULL,
    opened_at               TIMESTAMP,
    first_resolved_at       TIMESTAMP,
    last_resolved_at        TIMESTAMP,
    closed_at               TIMESTAMP,
    latest_state            TEXT,
    latest_priority         TEXT,
    latest_category         TEXT,
    latest_assignment_group TEXT,
    opening_priority        TEXT,
    opening_category        TEXT,
    opening_assignment_group TEXT,
    reopen_observed         BOOLEAN,
    latest_made_sla         BOOLEAN,
    event_count             INTEGER,
    batch_id_last           UUID,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_track, incident_number)
);

CREATE TABLE IF NOT EXISTS marts.ticket_open_features (
    source_track            TEXT NOT NULL,
    incident_number         TEXT NOT NULL,
    feature_cutoff          TIMESTAMP NOT NULL,
    snapshot_kind           TEXT NOT NULL,
    opened_at               TIMESTAMP,
    open_weekday            SMALLINT,
    open_hour               SMALLINT,
    impact                  TEXT,
    urgency                 TEXT,
    priority                TEXT,
    category                TEXT,
    subcategory             TEXT,
    contact_type            TEXT,
    initial_assignment_group TEXT,
    eligible                BOOLEAN NOT NULL DEFAULT TRUE,
    exclusion_reason        TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_track, incident_number)
);

CREATE TABLE IF NOT EXISTS marts.ticket_state_history (
    source_track        TEXT NOT NULL,
    incident_number     TEXT NOT NULL,
    state               TEXT NOT NULL,
    valid_from          TIMESTAMP NOT NULL,
    valid_to            TIMESTAMP,
    batch_id            UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_track, incident_number, valid_from, state)
);

CREATE TABLE IF NOT EXISTS marts.daily_volume (
    source_track        TEXT NOT NULL,
    arrival_date        DATE NOT NULL,
    distinct_arrivals   INTEGER NOT NULL,
    coverage_status     TEXT NOT NULL DEFAULT 'observed',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_track, arrival_date)
);

CREATE TABLE IF NOT EXISTS marts.daily_backlog (
    source_track        TEXT NOT NULL,
    as_of_date          DATE NOT NULL,
    observed_backlog    INTEGER NOT NULL,
    completeness_flag   TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_track, as_of_date)
);

CREATE TABLE IF NOT EXISTS marts.resolution_stats (
    source_track        TEXT NOT NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    category            TEXT NOT NULL,
    priority            TEXT NOT NULL,
    assignment_group    TEXT NOT NULL,
    n_eligible          INTEGER NOT NULL,
    n_missing_outcome   INTEGER NOT NULL,
    median_hours        DOUBLE PRECISION,
    p90_hours           DOUBLE PRECISION,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_track, period_start, period_end, category, priority, assignment_group)
);

CREATE TABLE IF NOT EXISTS models.model_registry (
    model_version       TEXT PRIMARY KEY,
    model_family        TEXT NOT NULL,
    source_track        TEXT NOT NULL,
    feature_contract    TEXT NOT NULL,
    dataset_snapshot_id TEXT,
    environment         TEXT,
    artifact_uri        TEXT,
    selection_status    TEXT NOT NULL DEFAULT 'candidate',
    metrics_json        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS models.evaluation_results (
    evaluation_id       BIGSERIAL PRIMARY KEY,
    model_version       TEXT NOT NULL REFERENCES models.model_registry (model_version),
    fold_id             TEXT,
    horizon_days        INTEGER,
    metric_name         TEXT NOT NULL,
    metric_value        DOUBLE PRECISION,
    details_json        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS models.forecast_predictions (
    prediction_id       BIGSERIAL PRIMARY KEY,
    model_version       TEXT NOT NULL REFERENCES models.model_registry (model_version),
    source_track        TEXT NOT NULL,
    issue_date          DATE NOT NULL,
    target_date         DATE NOT NULL,
    predicted_count     DOUBLE PRECISION NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_version, source_track, issue_date, target_date)
);

CREATE TABLE IF NOT EXISTS models.sla_risk_predictions (
    prediction_id       BIGSERIAL PRIMARY KEY,
    model_version       TEXT NOT NULL REFERENCES models.model_registry (model_version),
    source_track        TEXT NOT NULL,
    incident_number     TEXT NOT NULL,
    feature_cutoff      TIMESTAMP NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    threshold           DOUBLE PRECISION,
    compatible          BOOLEAN NOT NULL DEFAULT TRUE,
    scored_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_version, source_track, incident_number, feature_cutoff)
);

CREATE TABLE IF NOT EXISTS ops.export_releases (
    release_id          UUID PRIMARY KEY,
    source_tracks       TEXT[] NOT NULL,
    status              TEXT NOT NULL,
    manifest_uri        TEXT,
    row_counts_json     JSONB,
    checksums_json      JSONB,
    is_latest_good      BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
