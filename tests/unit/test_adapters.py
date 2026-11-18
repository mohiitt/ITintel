"""Unit tests for source adapter discovery contract."""

from pathlib import Path

from itintel.ingestion.adapters import LocalFileAdapter, sha256_path


def test_local_adapter_discovers_csv(tmp_path: Path) -> None:
    csv = tmp_path / "sample.csv"
    csv.write_text("number,opened_at\nINC1,01/03/2016 10:00\n")
    adapter = LocalFileAdapter(tmp_path)
    objects = adapter.list_objects("synthetic_quality")
    assert len(objects) == 1
    obj = objects[0]
    assert obj.display_name == "sample.csv"
    assert obj.content_sha256 == sha256_path(csv)
    assert obj.source_track == "synthetic_quality"
    assert obj.size_bytes == csv.stat().st_size


def test_local_adapter_empty_dir(tmp_path: Path) -> None:
    adapter = LocalFileAdapter(tmp_path)
    assert adapter.list_objects("public_historical") == []
