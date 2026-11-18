# ADR 0002 — Architecture and stack

**Status:** Accepted  
**Date:** 2026-11-18

## Decision

- One Python application (`src/itintel`) with plain SQL transformations in PostgreSQL.
- Docker Compose for local PostgreSQL + pipeline runtime; Supercronic scheduled later (Phase 10).
- Source adapters (local filesystem, S3) share one internal batch contract.
- Schema changes via versioned SQL migrations; repeatable transforms are separate.
- dbt, Terraform, RDS, Kubernetes, custom React UI, streaming, and text clustering are out of scope unless explicitly reopened.
- Tableau Public consumes versioned CSV exports (manual refresh), not a live DB connection.

## Time conventions

| Clock | Meaning |
| --- | --- |
| Event time | Source timestamps (`opened_at`, `sys_updated_at`, …) without inventing a timezone |
| Source collection time | Upstream export / object version time when known |
| Ingestion time | When the pipeline loaded the batch (`loaded_at`) |
| Publication time | When an export release was marked complete |

Analysis may assume a documented convention (treat timestamps as naive local wall-clock) without claiming the original timezone is known.
