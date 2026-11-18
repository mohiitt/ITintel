"""Configuration loading — secrets stay in environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config" / "default.yaml"


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password}"
        )

    def safe_summary(self) -> str:
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True)
class AppConfig:
    log_level: str
    source_track: str
    local_source_dir: Path
    analysis_tz_label: str
    timestamp_format: str
    missing_markers: tuple[str, ...]
    forecast_primary_track: str
    forecast_horizon_days: int
    sla_enabled: bool
    export_dir: Path
    database: DatabaseConfig
    s3_bucket: str | None = None
    s3_prefix: str | None = None
    extra: dict = field(default_factory=dict)


def load_config(
    config_path: Path | None = None,
    *,
    env_file: Path | None = ROOT / ".env",
) -> AppConfig:
    if env_file and env_file.exists():
        load_dotenv(env_file)

    path = config_path or Path(os.environ.get("ITINTEL_CONFIG", DEFAULT_CONFIG_PATH))
    raw: dict = {}
    if path.exists():
        with path.open() as f:
            raw = yaml.safe_load(f) or {}

    db_raw = raw.get("database", {})
    source_raw = raw.get("source", {})
    time_raw = raw.get("time", {})
    forecast_raw = raw.get("forecast", {})
    sla_raw = raw.get("sla", {})
    export_raw = raw.get("export", {})
    app_raw = raw.get("app", {})

    database = DatabaseConfig(
        host=os.environ.get("POSTGRES_HOST", db_raw.get("host", "localhost")),
        port=int(os.environ.get("POSTGRES_PORT", db_raw.get("port", 5432))),
        name=os.environ.get("POSTGRES_DB", db_raw.get("name", "itintel")),
        user=os.environ.get("POSTGRES_USER", db_raw.get("user", "itintel")),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )

    markers = time_raw.get("missing_markers", ["", "?"])
    return AppConfig(
        log_level=os.environ.get("ITINTEL_LOG_LEVEL", app_raw.get("log_level", "INFO")),
        source_track=os.environ.get(
            "ITINTEL_SOURCE_TRACK", source_raw.get("track", "public_historical")
        ),
        local_source_dir=Path(
            os.environ.get(
                "ITINTEL_LOCAL_SOURCE_DIR", source_raw.get("local_dir", "./data/raw")
            )
        ),
        analysis_tz_label=os.environ.get(
            "ITINTEL_ANALYSIS_TZ_LABEL",
            time_raw.get("analysis_tz_label", "unknown_naive_wall_clock"),
        ),
        timestamp_format=time_raw.get("timestamp_format", "%d/%m/%Y %H:%M"),
        missing_markers=tuple(markers),
        forecast_primary_track=forecast_raw.get("primary_track", "synthetic_campus"),
        forecast_horizon_days=int(
            os.environ.get(
                "ITINTEL_FORECAST_HORIZON_DAYS",
                forecast_raw.get("horizon_days", 7),
            )
        ),
        sla_enabled=bool(sla_raw.get("enabled", False)),
        export_dir=Path(export_raw.get("output_dir", "./data/releases")),
        database=database,
        s3_bucket=os.environ.get("ITINTEL_S3_BUCKET") or None,
        s3_prefix=os.environ.get("ITINTEL_S3_PREFIX") or None,
    )
