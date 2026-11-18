-- Migration 0001: create schemas
-- Idempotent schema creation for a fresh environment.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS quarantine;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS models;
CREATE SCHEMA IF NOT EXISTS ops;

COMMENT ON SCHEMA raw IS 'Immutable-ish ingested source rows (text fields)';
COMMENT ON SCHEMA staging IS 'Canonical typed event history';
COMMENT ON SCHEMA quarantine IS 'Rejected rows and rule violations';
COMMENT ON SCHEMA marts IS 'Analytical ticket and operational aggregates';
COMMENT ON SCHEMA models IS 'Model registry, evaluations, and predictions';
COMMENT ON SCHEMA ops IS 'Ingestion batches, DQ, and export releases';
