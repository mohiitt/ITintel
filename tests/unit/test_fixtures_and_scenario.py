"""Phase 2 fixture and campus scenario reproducibility."""

from pathlib import Path

from itintel.ingestion.campus_scenario import CampusScenarioSpec, generate_daily_arrivals
from itintel.ingestion.fixtures import generate_quality_fixtures


def test_quality_fixtures_are_deterministic(tmp_path: Path) -> None:
    a = generate_quality_fixtures(tmp_path / "a")
    b = generate_quality_fixtures(tmp_path / "b")
    assert [p.name for p in a] == [p.name for p in b]
    for pa, pb in zip(a, b, strict=True):
        assert pa.read_bytes() == pb.read_bytes()


def test_campus_scenario_reproducible_from_seed() -> None:
    s = CampusScenarioSpec(seed=99, days=30)
    d1 = generate_daily_arrivals(s)
    d2 = generate_daily_arrivals(s)
    assert d1.equals(d2)
    assert d1["source_track"].unique().tolist() == ["synthetic_campus"]
    assert int(d1["distinct_arrivals"].sum()) > 0
