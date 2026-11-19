"""Data-quality rule catalog (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

RULE_VERSION = "1.0.0"
TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M"
MISSING_MARKERS = frozenset({"", "?", "NA", "N/A", "null", "NULL", "None"})


@dataclass(frozen=True)
class RuleDef:
    rule_id: str
    severity: str  # fatal | warning | batch_fail
    explanation: str
    owner_action: str


RULES: dict[str, RuleDef] = {
    "batch.missing_required_columns": RuleDef(
        "batch.missing_required_columns",
        "batch_fail",
        "Required columns missing from the file header.",
        "Reject batch; retain last good export.",
    ),
    "identity.missing_incident_number": RuleDef(
        "identity.missing_incident_number",
        "fatal",
        "Incident identifier is missing or a missing-value marker.",
        "Quarantine the row.",
    ),
    "parsing.required_opened_at": RuleDef(
        "parsing.required_opened_at",
        "fatal",
        "Required opened_at is missing or unparseable.",
        "Quarantine the row.",
    ),
    "parsing.required_sys_updated_at": RuleDef(
        "parsing.required_sys_updated_at",
        "fatal",
        "Required sys_updated_at is missing or unparseable.",
        "Quarantine the row.",
    ),
    "parsing.optional_resolved_at": RuleDef(
        "parsing.optional_resolved_at",
        "warning",
        "Optional resolved_at is unparseable; null in staging and exclude duration metrics.",
        "Accept row with warning.",
    ),
    "parsing.optional_closed_at": RuleDef(
        "parsing.optional_closed_at",
        "warning",
        "Optional closed_at is unparseable; null in staging.",
        "Accept row with warning.",
    ),
    "temporal.resolution_before_opening": RuleDef(
        "temporal.resolution_before_opening",
        "warning",
        "resolved_at is before opened_at; reject invalid temporal contribution only.",
        "Null resolved_at in staging; log warning.",
    ),
    "temporal.closure_before_resolution": RuleDef(
        "temporal.closure_before_resolution",
        "warning",
        "closed_at is before resolved_at on the same row.",
        "Flag for review; keep both fields with warning.",
    ),
    "optional.unknown_category": RuleDef(
        "optional.unknown_category",
        "warning",
        "Category is a missing-value marker; map to explicit unknown bucket.",
        "Accept with unknown category.",
    ),
}


def is_missing(value: str | None) -> bool:
    if value is None:
        return True
    return str(value).strip() in MISSING_MARKERS


def parse_ts(value: str | None) -> datetime | None:
    if is_missing(value):
        return None
    try:
        return datetime.strptime(str(value).strip(), TIMESTAMP_FORMAT)
    except ValueError:
        return None


def parse_bool(value: str | None) -> bool | None:
    if is_missing(value):
        return None
    v = str(value).strip().lower()
    if v in {"true", "t", "1", "yes"}:
        return True
    if v in {"false", "f", "0", "no"}:
        return False
    return None


def parse_int(value: str | None) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


@dataclass
class Violation:
    rule_id: str
    severity: str
    field_name: str | None
    explanation: str


@dataclass
class RowAssessment:
    disposition: str  # accepted | accepted_with_warnings | quarantined
    violations: list[Violation]
    typed: dict[str, Any]


def assess_raw_row(row: dict[str, str]) -> RowAssessment:
    """Validate one raw text row and produce typed fields + disposition."""
    violations: list[Violation] = []
    typed: dict[str, Any] = {}

    number = (row.get("number") or "").strip()
    if is_missing(number):
        violations.append(
            Violation(
                "identity.missing_incident_number",
                "fatal",
                "number",
                RULES["identity.missing_incident_number"].explanation,
            )
        )
        typed["incident_number"] = None
    else:
        typed["incident_number"] = number

    opened_raw = row.get("opened_at")
    opened_at = parse_ts(opened_raw)
    if opened_at is None:
        violations.append(
            Violation(
                "parsing.required_opened_at",
                "fatal",
                "opened_at",
                RULES["parsing.required_opened_at"].explanation,
            )
        )
    typed["opened_at"] = opened_at

    updated_raw = row.get("sys_updated_at")
    updated_at = parse_ts(updated_raw)
    if updated_at is None:
        violations.append(
            Violation(
                "parsing.required_sys_updated_at",
                "fatal",
                "sys_updated_at",
                RULES["parsing.required_sys_updated_at"].explanation,
            )
        )
    typed["sys_updated_at"] = updated_at

    # Optional timestamps
    resolved_raw = row.get("resolved_at")
    if is_missing(resolved_raw):
        typed["resolved_at"] = None
    else:
        resolved_at = parse_ts(resolved_raw)
        if resolved_at is None:
            violations.append(
                Violation(
                    "parsing.optional_resolved_at",
                    "warning",
                    "resolved_at",
                    RULES["parsing.optional_resolved_at"].explanation,
                )
            )
            typed["resolved_at"] = None
        else:
            typed["resolved_at"] = resolved_at

    closed_raw = row.get("closed_at")
    if is_missing(closed_raw):
        typed["closed_at"] = None
    else:
        closed_at = parse_ts(closed_raw)
        if closed_at is None:
            violations.append(
                Violation(
                    "parsing.optional_closed_at",
                    "warning",
                    "closed_at",
                    RULES["parsing.optional_closed_at"].explanation,
                )
            )
            typed["closed_at"] = None
        else:
            typed["closed_at"] = closed_at

    if typed.get("opened_at") and typed.get("resolved_at"):
        if typed["resolved_at"] < typed["opened_at"]:
            violations.append(
                Violation(
                    "temporal.resolution_before_opening",
                    "warning",
                    "resolved_at",
                    RULES["temporal.resolution_before_opening"].explanation,
                )
            )
            typed["resolved_at"] = None

    if typed.get("resolved_at") and typed.get("closed_at"):
        if typed["closed_at"] < typed["resolved_at"]:
            violations.append(
                Violation(
                    "temporal.closure_before_resolution",
                    "warning",
                    "closed_at",
                    RULES["temporal.closure_before_resolution"].explanation,
                )
            )

    category = (row.get("category") or "").strip()
    if is_missing(category):
        violations.append(
            Violation(
                "optional.unknown_category",
                "warning",
                "category",
                RULES["optional.unknown_category"].explanation,
            )
        )
        typed["category"] = "UNKNOWN"
    else:
        typed["category"] = category

    typed.update(
        {
            "incident_state": row.get("incident_state") or None,
            "active": parse_bool(row.get("active")),
            "reassignment_count": parse_int(row.get("reassignment_count")),
            "reopen_count": parse_int(row.get("reopen_count")),
            "sys_mod_count": parse_int(row.get("sys_mod_count")),
            "made_sla": parse_bool(row.get("made_sla")),
            "sys_created_at": parse_ts(row.get("sys_created_at")),
            "contact_type": None if is_missing(row.get("contact_type")) else row.get("contact_type"),
            "subcategory": None if is_missing(row.get("subcategory")) else row.get("subcategory"),
            "impact": None if is_missing(row.get("impact")) else row.get("impact"),
            "urgency": None if is_missing(row.get("urgency")) else row.get("urgency"),
            "priority": None if is_missing(row.get("priority")) else row.get("priority"),
            "assignment_group": (
                None if is_missing(row.get("assignment_group")) else row.get("assignment_group")
            ),
            "assigned_to": None if is_missing(row.get("assigned_to")) else row.get("assigned_to"),
            "closed_code": None if is_missing(row.get("closed_code")) else row.get("closed_code"),
            "resolved_by": None if is_missing(row.get("resolved_by")) else row.get("resolved_by"),
        }
    )

    if any(v.severity == "fatal" for v in violations):
        disposition = "quarantined"
    elif violations:
        disposition = "accepted_with_warnings"
    else:
        disposition = "accepted"

    return RowAssessment(disposition=disposition, violations=violations, typed=typed)
