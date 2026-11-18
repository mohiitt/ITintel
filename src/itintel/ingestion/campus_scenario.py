"""Synthetic campus daily-arrival scenario generator (Phase 2 / forecast fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CampusScenarioSpec:
    seed: int = 20260301
    start: date = date(2026, 1, 5)
    days: int = 180
    base_weekday: tuple[float, ...] = (220, 240, 230, 225, 200, 40, 30)
    # Illustrative calendar labels — not an official SJSU calendar unless sourced.
    registration_burst: tuple[date, date] = (date(2026, 1, 12), date(2026, 1, 23))
    term_start: tuple[date, date] = (date(2026, 1, 26), date(2026, 2, 6))
    finals: tuple[date, date] = (date(2026, 5, 11), date(2026, 5, 22))
    noise_sigma: float = 18.0
    trend_per_day: float = 0.05
    calendar_label: str = "illustrative_campus_calendar_v1"


def _in_window(d: date, window: tuple[date, date]) -> bool:
    return window[0] <= d <= window[1]


def generate_daily_arrivals(spec: CampusScenarioSpec | None = None) -> pd.DataFrame:
    """Return a clean synthetic daily series with scenario labels.

    This measures generator assumptions, not observed SJSU demand.
    """
    spec = spec or CampusScenarioSpec()
    rng = np.random.default_rng(spec.seed)
    rows: list[dict] = []
    for i in range(spec.days):
        d = spec.start + timedelta(days=i)
        weekday = d.weekday()  # Mon=0
        level = spec.base_weekday[weekday] + spec.trend_per_day * i
        label = "baseline"
        if _in_window(d, spec.registration_burst):
            level *= 1.55
            label = "registration_burst"
        elif _in_window(d, spec.term_start):
            level *= 1.35
            label = "term_start"
        elif _in_window(d, spec.finals):
            level *= 1.45
            label = "finals"
        noise = float(rng.normal(0.0, spec.noise_sigma))
        arrivals = max(0, int(round(level + noise)))
        rows.append(
            {
                "arrival_date": d.isoformat(),
                "distinct_arrivals": arrivals,
                "weekday": weekday,
                "scenario_label": label,
                "source_track": "synthetic_campus",
                "calendar_label": spec.calendar_label,
                "seed": spec.seed,
            }
        )
    return pd.DataFrame(rows)


def write_campus_scenario(output_dir: Path, spec: CampusScenarioSpec | None = None) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = generate_daily_arrivals(spec)
    path = output_dir / "campus_daily_arrivals.csv"
    df.to_csv(path, index=False)
    meta = output_dir / "campus_scenario_meta.json"
    s = spec or CampusScenarioSpec()
    meta.write_text(
        pd.Series(
            {
                "seed": s.seed,
                "start": s.start.isoformat(),
                "days": s.days,
                "calendar_label": s.calendar_label,
                "disclaimer": (
                    "Illustrative synthetic campus workload. Not measured SJSU demand. "
                    "Must not mix into public_historical training or unlabeled KPIs."
                ),
            }
        ).to_json()
    )
    return path
