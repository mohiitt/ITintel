"""Build ticket marts from staging.incident_events (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from itintel.config import AppConfig, load_config
from itintel.db.connection import connect


@dataclass(frozen=True)
class MartsResult:
    source_track: str
    ticket_count: int
    daily_volume_days: int
    open_feature_count: int


def build_marts(source_track: str, *, config: AppConfig | None = None) -> MartsResult:
    """Recompute marts for one source track from canonical staging events."""
    cfg = config or load_config()
    now = datetime.now(UTC)

    with connect(cfg.database) as conn:
        # fact_tickets: one row per incident
        conn.execute(
            "DELETE FROM marts.fact_tickets WHERE source_track = %s",
            (source_track,),
        )
        conn.execute(
            """
            INSERT INTO marts.fact_tickets (
                source_track, incident_number, opened_at, first_resolved_at, last_resolved_at,
                closed_at, latest_state, latest_priority, latest_category, latest_assignment_group,
                opening_priority, opening_category, opening_assignment_group, reopen_observed,
                latest_made_sla, event_count, batch_id_last, created_at, updated_at
            )
            WITH ordered AS (
                SELECT
                    e.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY incident_number
                        ORDER BY sys_updated_at ASC NULLS LAST, file_row_number ASC
                    ) AS rn_asc,
                    ROW_NUMBER() OVER (
                        PARTITION BY incident_number
                        ORDER BY sys_updated_at DESC NULLS LAST, file_row_number DESC
                    ) AS rn_desc
                FROM staging.incident_events e
                WHERE source_track = %s
            ),
            agg AS (
                SELECT
                    incident_number,
                    MIN(opened_at) AS opened_at,
                    MIN(resolved_at) AS first_resolved_at,
                    MAX(resolved_at) AS last_resolved_at,
                    MAX(closed_at) AS closed_at,
                    BOOL_OR(COALESCE(reopen_count, 0) > 0) AS reopen_observed,
                    COUNT(*) AS event_count,
                    MAX(batch_id::text)::uuid AS batch_id_last
                FROM ordered
                GROUP BY incident_number
            ),
            first_row AS (
                SELECT incident_number, priority AS opening_priority,
                       category AS opening_category,
                       assignment_group AS opening_assignment_group
                FROM ordered WHERE rn_asc = 1
            ),
            last_row AS (
                SELECT incident_number, incident_state AS latest_state,
                       priority AS latest_priority, category AS latest_category,
                       assignment_group AS latest_assignment_group,
                       made_sla AS latest_made_sla
                FROM ordered WHERE rn_desc = 1
            )
            SELECT
                %s,
                a.incident_number,
                a.opened_at,
                a.first_resolved_at,
                a.last_resolved_at,
                a.closed_at,
                l.latest_state,
                l.latest_priority,
                l.latest_category,
                l.latest_assignment_group,
                f.opening_priority,
                f.opening_category,
                f.opening_assignment_group,
                a.reopen_observed,
                l.latest_made_sla,
                a.event_count,
                a.batch_id_last,
                %s,
                %s
            FROM agg a
            JOIN first_row f USING (incident_number)
            JOIN last_row l USING (incident_number)
            """,
            (source_track, source_track, now, now),
        )

        # Opening features — allowlisted fields from earliest snapshot only.
        # Exclude outcome-revealing fields; mark ineligible if opened_at missing.
        conn.execute(
            "DELETE FROM marts.ticket_open_features WHERE source_track = %s",
            (source_track,),
        )
        conn.execute(
            """
            INSERT INTO marts.ticket_open_features (
                source_track, incident_number, feature_cutoff, snapshot_kind,
                opened_at, open_weekday, open_hour, impact, urgency, priority,
                category, subcategory, contact_type, initial_assignment_group,
                eligible, exclusion_reason, created_at, updated_at
            )
            WITH earliest AS (
                SELECT DISTINCT ON (incident_number)
                    incident_number, opened_at, sys_updated_at, impact, urgency, priority,
                    category, subcategory, contact_type, assignment_group
                FROM staging.incident_events
                WHERE source_track = %s
                ORDER BY incident_number, sys_updated_at ASC NULLS LAST, file_row_number ASC
            )
            SELECT
                %s,
                incident_number,
                COALESCE(sys_updated_at, opened_at),
                'first_observed_snapshot',
                opened_at,
                EXTRACT(DOW FROM opened_at)::smallint,
                EXTRACT(HOUR FROM opened_at)::smallint,
                impact,
                urgency,
                priority,
                category,
                subcategory,
                contact_type,
                assignment_group,
                (opened_at IS NOT NULL),
                CASE WHEN opened_at IS NULL THEN 'missing_opened_at' ELSE NULL END,
                %s,
                %s
            FROM earliest
            """,
            (source_track, source_track, now, now),
        )

        # State history: emit only when state changes (collapse same-timestamp duplicates).
        conn.execute(
            "DELETE FROM marts.ticket_state_history WHERE source_track = %s",
            (source_track,),
        )
        conn.execute(
            """
            INSERT INTO marts.ticket_state_history (
                source_track, incident_number, state, valid_from, valid_to, batch_id, created_at
            )
            WITH ordered AS (
                SELECT
                    incident_number,
                    COALESCE(incident_state, 'UNKNOWN') AS state,
                    sys_updated_at,
                    batch_id,
                    file_row_number,
                    LAG(COALESCE(incident_state, 'UNKNOWN')) OVER (
                        PARTITION BY incident_number
                        ORDER BY sys_updated_at, file_row_number
                    ) AS prev_state
                FROM staging.incident_events
                WHERE source_track = %s
                  AND sys_updated_at IS NOT NULL
            ),
            changes AS (
                SELECT *
                FROM ordered
                WHERE prev_state IS NULL OR state <> prev_state
            )
            SELECT
                %s,
                incident_number,
                state,
                sys_updated_at,
                LEAD(sys_updated_at) OVER (
                    PARTITION BY incident_number ORDER BY sys_updated_at, file_row_number
                ),
                batch_id,
                %s
            FROM changes
            """,
            (source_track, source_track, now),
        )

        # Daily volume — observed arrivals only (no invented zeros)
        conn.execute(
            "DELETE FROM marts.daily_volume WHERE source_track = %s",
            (source_track,),
        )
        conn.execute(
            """
            INSERT INTO marts.daily_volume (
                source_track, arrival_date, distinct_arrivals, coverage_status, created_at, updated_at
            )
            SELECT
                %s,
                opened_at::date,
                COUNT(*)::int,
                'observed',
                %s,
                %s
            FROM marts.fact_tickets
            WHERE source_track = %s
              AND opened_at IS NOT NULL
            GROUP BY opened_at::date
            """,
            (source_track, now, now, source_track),
        )

        # Observed backlog: openings cumulative minus closures cumulative (labeled incomplete).
        conn.execute(
            "DELETE FROM marts.daily_backlog WHERE source_track = %s",
            (source_track,),
        )
        conn.execute(
            """
            INSERT INTO marts.daily_backlog (
                source_track, as_of_date, observed_backlog, completeness_flag,
                created_at, updated_at
            )
            WITH opens AS (
                SELECT opened_at::date AS d, COUNT(*)::int AS n
                FROM marts.fact_tickets
                WHERE source_track = %s AND opened_at IS NOT NULL
                GROUP BY 1
            ),
            closes AS (
                SELECT closed_at::date AS d, COUNT(*)::int AS n
                FROM marts.fact_tickets
                WHERE source_track = %s AND closed_at IS NOT NULL
                GROUP BY 1
            ),
            days AS (
                SELECT arrival_date AS d FROM marts.daily_volume WHERE source_track = %s
                UNION
                SELECT d FROM closes
            ),
            series AS (
                SELECT
                    d.d,
                    COALESCE(o.n, 0) AS opened,
                    COALESCE(c.n, 0) AS closed
                FROM days d
                LEFT JOIN opens o ON o.d = d.d
                LEFT JOIN closes c ON c.d = d.d
            )
            SELECT
                %s,
                d,
                SUM(opened - closed) OVER (ORDER BY d)::int,
                'observed_incomplete_prehistory',
                %s,
                %s
            FROM series
            WHERE d IN (SELECT arrival_date FROM marts.daily_volume WHERE source_track = %s)
            """,
            (source_track, source_track, source_track, source_track, now, now, source_track),
        )

        # Resolution stats by category/priority (overall window)
        conn.execute(
            "DELETE FROM marts.resolution_stats WHERE source_track = %s",
            (source_track,),
        )
        conn.execute(
            """
            INSERT INTO marts.resolution_stats (
                source_track, period_start, period_end, category, priority, assignment_group,
                n_eligible, n_missing_outcome, median_hours, p90_hours, created_at, updated_at
            )
            SELECT
                %s,
                MIN(opened_at)::date,
                MAX(opened_at)::date,
                COALESCE(opening_category, 'UNKNOWN'),
                COALESCE(opening_priority, 'UNKNOWN'),
                COALESCE(opening_assignment_group, 'UNKNOWN'),
                COUNT(*) FILTER (WHERE first_resolved_at IS NOT NULL)::int,
                COUNT(*) FILTER (WHERE first_resolved_at IS NULL)::int,
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (first_resolved_at - opened_at)) / 3600.0
                ) FILTER (WHERE first_resolved_at IS NOT NULL AND first_resolved_at >= opened_at),
                PERCENTILE_CONT(0.9) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (first_resolved_at - opened_at)) / 3600.0
                ) FILTER (WHERE first_resolved_at IS NOT NULL AND first_resolved_at >= opened_at),
                %s,
                %s
            FROM marts.fact_tickets
            WHERE source_track = %s
              AND opened_at IS NOT NULL
            GROUP BY
                COALESCE(opening_category, 'UNKNOWN'),
                COALESCE(opening_priority, 'UNKNOWN'),
                COALESCE(opening_assignment_group, 'UNKNOWN')
            """,
            (source_track, now, now, source_track),
        )

        # Advance batches for this track that were validating
        conn.execute(
            """
            UPDATE ops.ingestion_batches
            SET state = 'transformed', updated_at = %s
            WHERE source_track = %s AND state = 'validating'
            """,
            (now, source_track),
        )

        ticket_count = conn.execute(
            "SELECT COUNT(*) FROM marts.fact_tickets WHERE source_track = %s",
            (source_track,),
        ).fetchone()[0]
        daily_days = conn.execute(
            "SELECT COUNT(*) FROM marts.daily_volume WHERE source_track = %s",
            (source_track,),
        ).fetchone()[0]
        open_feats = conn.execute(
            "SELECT COUNT(*) FROM marts.ticket_open_features WHERE source_track = %s",
            (source_track,),
        ).fetchone()[0]
        conn.commit()

    return MartsResult(
        source_track=source_track,
        ticket_count=int(ticket_count),
        daily_volume_days=int(daily_days),
        open_feature_count=int(open_feats),
    )
