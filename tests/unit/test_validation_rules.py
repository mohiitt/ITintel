"""Unit tests for Phase 4 validation rules."""

from itintel.validation.rules import assess_raw_row


def _base(**overrides: str) -> dict[str, str]:
    row = {
        "number": "INC1",
        "opened_at": "01/03/2016 10:00",
        "sys_updated_at": "01/03/2016 10:05",
        "resolved_at": "?",
        "closed_at": "?",
        "category": "Category 1",
        "incident_state": "New",
        "active": "true",
        "reassignment_count": "0",
        "reopen_count": "0",
        "sys_mod_count": "0",
        "made_sla": "true",
        "impact": "3 - Low",
        "urgency": "3 - Low",
        "priority": "3 - Low",
        "assignment_group": "Group 1",
        "contact_type": "Phone",
        "subcategory": "Sub 1",
        "assigned_to": "A1",
        "closed_code": "?",
        "resolved_by": "?",
        "sys_created_at": "01/03/2016 10:01",
    }
    row.update(overrides)
    return row


def test_missing_incident_quarantines() -> None:
    a = assess_raw_row(_base(number="?"))
    assert a.disposition == "quarantined"
    assert any(v.rule_id == "identity.missing_incident_number" for v in a.violations)


def test_unparseable_resolved_accepts_with_warning() -> None:
    a = assess_raw_row(_base(resolved_at="not-a-date"))
    assert a.disposition == "accepted_with_warnings"
    assert a.typed["resolved_at"] is None


def test_resolution_before_opening_nulls_resolved() -> None:
    a = assess_raw_row(
        _base(opened_at="01/03/2016 12:00", resolved_at="01/03/2016 11:00")
    )
    assert a.disposition == "accepted_with_warnings"
    assert a.typed["resolved_at"] is None


def test_valid_row_accepted() -> None:
    a = assess_raw_row(_base())
    assert a.disposition == "accepted"
