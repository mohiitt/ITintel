"""Deterministic synthetic quality fixture generator (Phase 2)."""

from __future__ import annotations

import csv
from pathlib import Path

from itintel.common import RAW_COLUMN_NAMES

# Minimal valid row template (text fields matching UCI physical schema).
_BASE = {c: "" for c in RAW_COLUMN_NAMES}
_BASE.update(
    {
        "number": "INC0000001",
        "incident_state": "New",
        "active": "true",
        "reassignment_count": "0",
        "reopen_count": "0",
        "sys_mod_count": "0",
        "made_sla": "true",
        "caller_id": "Caller 1",
        "opened_by": "Opened by 1",
        "opened_at": "01/03/2016 10:00",
        "sys_created_by": "Created by 1",
        "sys_created_at": "01/03/2016 10:01",
        "sys_updated_by": "Updated by 1",
        "sys_updated_at": "01/03/2016 10:05",
        "contact_type": "Phone",
        "location": "Location 1",
        "category": "Category 1",
        "subcategory": "Subcategory 1",
        "impact": "3 - Low",
        "urgency": "3 - Low",
        "priority": "3 - Low",
        "assignment_group": "Group 1",
        "assigned_to": "Resolver 1",
        "knowledge": "false",
        "u_priority_confirmation": "false",
        "notify": "Do Not Notify",
        "closed_code": "?",
        "resolved_by": "?",
        "resolved_at": "?",
        "closed_at": "?",
    }
)


def _row(**overrides: str) -> dict[str, str]:
    out = dict(_BASE)
    out.update(overrides)
    return out


def _write(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    cols = columns or list(RAW_COLUMN_NAMES)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in cols})


def generate_quality_fixtures(output_dir: Path) -> list[Path]:
    """Write deterministic fixture CSVs. Seed is fixed by construction (no RNG)."""
    written: list[Path] = []

    p = output_dir / "missing_incident_id.csv"
    _write(p, [_row(number="")])
    written.append(p)

    p = output_dir / "missing_opened_at.csv"
    _write(p, [_row(opened_at="?")])
    written.append(p)

    p = output_dir / "unparseable_resolved_at.csv"
    _write(
        p,
        [
            _row(
                number="INC0000002",
                resolved_at="not-a-date",
                incident_state="Active",
                sys_updated_at="01/03/2016 11:00",
            )
        ],
    )
    written.append(p)

    p = output_dir / "resolution_before_opening.csv"
    _write(
        p,
        [
            _row(
                number="INC0000003",
                opened_at="01/03/2016 12:00",
                resolved_at="01/03/2016 11:00",
                closed_at="01/03/2016 11:30",
                incident_state="Resolved",
                sys_updated_at="01/03/2016 12:05",
            )
        ],
    )
    written.append(p)

    p = output_dir / "valid_incident_update.csv"
    _write(
        p,
        [
            _row(number="INC0000010", incident_state="New", sys_updated_at="01/03/2016 10:05"),
            _row(
                number="INC0000010",
                incident_state="Active",
                sys_mod_count="1",
                sys_updated_at="01/03/2016 11:00",
                assignment_group="Group 2",
            ),
        ],
    )
    written.append(p)

    p = output_dir / "exact_duplicate_rows.csv"
    dup = _row(number="INC0000020", sys_updated_at="01/03/2016 10:05")
    _write(p, [dup, dict(dup)])
    written.append(p)

    # Missing required column: omit `number` from header entirely.
    p = output_dir / "missing_required_column.csv"
    cols = [c for c in RAW_COLUMN_NAMES if c != "number"]
    _write(p, [_row()], columns=cols)
    written.append(p)

    return written
