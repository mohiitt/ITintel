"""Config loading without requiring a live database."""

from itintel.config import load_config


def test_load_default_config() -> None:
    cfg = load_config(env_file=None)
    assert cfg.forecast_primary_track == "synthetic_campus"
    assert cfg.forecast_horizon_days == 7
    assert cfg.sla_enabled is False
    assert cfg.timestamp_format == "%d/%m/%Y %H:%M"
    assert "public_historical" in cfg.source_track or cfg.source_track
