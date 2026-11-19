"""Validate a loaded raw batch: quarantine fatals, stage accepted rows, record DQ."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from itintel.config import AppConfig, load_config
from itintel.db.connection import connect
from itintel.validation.rules import RULE_VERSION, RULES, assess_raw_row


@dataclass(frozen=True)
class ValidateResult:
    batch_id: str
    dq_run_id: str
    status: str
    rows_checked: int
    rows_accepted: int
    rows_quarantined: int
    warning_count: int


def validate_batch(
    batch_id: str,
    *,
    config: AppConfig | None = None,
    force: bool = False,
) -> ValidateResult:
    cfg = config or load_config()
    dq_run_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    with connect(cfg.database) as conn:
        batch = conn.execute(
            """
            SELECT source_track, state
            FROM ops.ingestion_batches
            WHERE batch_id = %s
            """,
            (batch_id,),
        ).fetchone()
        if not batch:
            raise ValueError(f"Unknown batch_id={batch_id}")
        source_track, state = batch
        if state in {"transformed", "exported"} and not force:
            return ValidateResult(
                batch_id=batch_id,
                dq_run_id="",
                status="skipped_already_transformed",
                rows_checked=0,
                rows_accepted=0,
                rows_quarantined=0,
                warning_count=0,
            )

        conn.execute(
            "UPDATE ops.ingestion_batches SET state = 'validating', updated_at = %s WHERE batch_id = %s",
            (now, batch_id),
        )
        conn.execute(
            "DELETE FROM quarantine.row_violations WHERE quarantine_id IN "
            "(SELECT quarantine_id FROM quarantine.incident_rows WHERE batch_id = %s)",
            (batch_id,),
        )
        conn.execute("DELETE FROM quarantine.incident_rows WHERE batch_id = %s", (batch_id,))
        conn.execute("DELETE FROM ops.row_quality_issues WHERE batch_id = %s", (batch_id,))
        conn.execute("DELETE FROM staging.incident_events WHERE batch_id = %s", (batch_id,))
        # Drop prior dq_runs check results for this batch (keep history light for portfolio)
        conn.execute(
            "DELETE FROM ops.dq_check_results WHERE dq_run_id IN "
            "(SELECT dq_run_id FROM ops.dq_runs WHERE batch_id = %s)",
            (batch_id,),
        )
        conn.execute("DELETE FROM ops.dq_runs WHERE batch_id = %s", (batch_id,))
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT file_row_number, number, incident_state, active, reassignment_count,
                       reopen_count, sys_mod_count, made_sla, opened_at, sys_created_at,
                       sys_updated_at, contact_type, category, subcategory, impact, urgency,
                       priority, assignment_group, assigned_to, closed_code, resolved_by,
                       resolved_at, closed_at
                FROM raw.incident_rows
                WHERE batch_id = %s
                ORDER BY file_row_number
                """,
                (batch_id,),
            )
            colnames = [d.name for d in cur.description]
            raw_tuples = cur.fetchall()
        df = pd.DataFrame(raw_tuples, columns=colnames)

    # Assess in-process (no DB chatter per row)
    accepted_rows: list[dict] = []
    quarantine_rows: list[tuple] = []  # (file_row_number, primary_rule, violations)
    warning_issues: list[tuple] = []
    rule_stats: dict[str, int] = {}
    warning_count = 0

    records = df.fillna("").astype(str).to_dict(orient="records")
    for row in records:
        file_row_number = int(float(row["file_row_number"]))
        assessment = assess_raw_row(row)
        for v in assessment.violations:
            rule_stats[v.rule_id] = rule_stats.get(v.rule_id, 0) + 1
            if v.severity == "warning":
                warning_count += 1
                warning_issues.append(
                    (
                        batch_id,
                        file_row_number,
                        v.rule_id,
                        RULE_VERSION,
                        v.severity,
                        v.field_name,
                        v.explanation,
                    )
                )
        if assessment.disposition == "quarantined":
            primary = next(v for v in assessment.violations if v.severity == "fatal")
            quarantine_rows.append((file_row_number, primary.rule_id, assessment.violations))
            continue
        t = assessment.typed
        accepted_rows.append(
            {
                "source_track": source_track,
                "batch_id": batch_id,
                "file_row_number": file_row_number,
                "incident_number": t["incident_number"],
                "incident_state": t.get("incident_state"),
                "active": t.get("active"),
                "reassignment_count": t.get("reassignment_count"),
                "reopen_count": t.get("reopen_count"),
                "sys_mod_count": t.get("sys_mod_count"),
                "made_sla": t.get("made_sla"),
                "opened_at": t.get("opened_at"),
                "sys_created_at": t.get("sys_created_at"),
                "sys_updated_at": t.get("sys_updated_at"),
                "resolved_at": t.get("resolved_at"),
                "closed_at": t.get("closed_at"),
                "contact_type": t.get("contact_type"),
                "category": t.get("category"),
                "subcategory": t.get("subcategory"),
                "impact": t.get("impact"),
                "urgency": t.get("urgency"),
                "priority": t.get("priority"),
                "assignment_group": t.get("assignment_group"),
                "assigned_to": t.get("assigned_to"),
                "closed_code": t.get("closed_code"),
                "resolved_by": t.get("resolved_by"),
                "event_identity_key": (
                    f"{source_track}|{t['incident_number']}|{file_row_number}|{batch_id}"
                ),
            }
        )

    accepted = len(accepted_rows)
    quarantined = len(quarantine_rows)
    status = "passed" if quarantined == 0 else "passed_with_quarantine"
    if accepted == 0 and quarantined > 0:
        status = "failed"

    with connect(cfg.database) as conn:
        if warning_issues:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO ops.row_quality_issues
                        (batch_id, file_row_number, rule_id, rule_version, severity,
                         field_name, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    warning_issues,
                )

        for file_row_number, primary_rule, violations in quarantine_rows:
            qid = conn.execute(
                """
                INSERT INTO quarantine.incident_rows
                    (batch_id, file_row_number, primary_rule_id, disposition)
                VALUES (%s, %s, %s, 'quarantined')
                RETURNING quarantine_id
                """,
                (batch_id, file_row_number, primary_rule),
            ).fetchone()[0]
            for v in violations:
                conn.execute(
                    """
                    INSERT INTO quarantine.row_violations
                        (quarantine_id, rule_id, rule_version, severity, field_name, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (qid, v.rule_id, RULE_VERSION, v.severity, v.field_name, v.explanation),
                )

        if accepted_rows:
            cols = list(accepted_rows[0].keys())
            with conn.cursor() as cur:
                with cur.copy(
                    f"COPY staging.incident_events ({', '.join(cols)}) FROM STDIN"
                ) as copy:
                    for r in accepted_rows:
                        copy.write_row(tuple(r[c] for c in cols))

        conn.execute(
            """
            INSERT INTO ops.dq_runs (
                dq_run_id, batch_id, source_track, status, rows_checked,
                rows_accepted, rows_quarantined, rows_excluded_dup, started_at, finished_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
            """,
            (
                dq_run_id,
                batch_id,
                source_track,
                status,
                len(records),
                accepted,
                quarantined,
                now,
                datetime.now(UTC),
            ),
        )
        for rule_id, failures in rule_stats.items():
            rule = RULES.get(rule_id)
            conn.execute(
                """
                INSERT INTO ops.dq_check_results (
                    dq_run_id, rule_id, rule_version, scope, status,
                    rows_checked, failure_count, distinct_affected, details
                ) VALUES (%s, %s, %s, 'batch', %s, %s, %s, %s, %s)
                """,
                (
                    dq_run_id,
                    rule_id,
                    RULE_VERSION,
                    "fail" if failures else "pass",
                    len(records),
                    failures,
                    failures,
                    rule.explanation if rule else None,
                ),
            )

        finished = datetime.now(UTC)
        new_state = "failed" if status == "failed" else "validating"
        conn.execute(
            """
            UPDATE ops.ingestion_batches
            SET state = %s, accepted_count = %s, quarantined_count = %s, updated_at = %s
            WHERE batch_id = %s
            """,
            (new_state, accepted, quarantined, finished, batch_id),
        )
        conn.commit()

    return ValidateResult(
        batch_id=batch_id,
        dq_run_id=dq_run_id,
        status=status,
        rows_checked=len(records),
        rows_accepted=accepted,
        rows_quarantined=quarantined,
        warning_count=warning_count,
    )
