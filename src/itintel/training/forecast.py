"""Ticket-volume forecasting on synthetic campus track (Phase 7)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from itintel.config import ROOT, AppConfig, load_config
from itintel.db.connection import connect
from itintel.ingestion.campus_scenario import CampusScenarioSpec, generate_daily_arrivals

ARTIFACT_DIR = ROOT / "data" / "processed" / "models"


@dataclass
class ForecastEvalRow:
    fold_id: str
    issue_date: str
    model: str
    mae: float
    wape: float | None
    baseline_mae: float
    improvement_vs_baseline: float | None
    n_days: int


@dataclass
class ForecastRunResult:
    model_version: str
    source_track: str
    horizon_days: int
    selected_model: str
    evaluations: list[ForecastEvalRow]
    next_seven: list[dict]


def _wape(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    denom = float(np.sum(np.abs(y_true)))
    if denom == 0:
        return None
    return float(np.sum(np.abs(y_true - y_pred)) / denom)


def seasonal_naive(history: pd.Series, issue_date: date, horizon: int) -> np.ndarray:
    """Same-weekday-last-week for each of the next `horizon` days."""
    preds = []
    for h in range(1, horizon + 1):
        target = issue_date + timedelta(days=h)
        lookback = target - timedelta(days=7)
        if lookback in history.index:
            preds.append(float(history.loc[lookback]))
        else:
            # fall back to last available same weekday
            same = history[history.index.weekday == target.weekday()]
            preds.append(float(same.iloc[-1]) if len(same) else float(history.iloc[-1]))
    return np.asarray(preds, dtype=float)


def moving_average(history: pd.Series, issue_date: date, horizon: int, window: int = 14) -> np.ndarray:
    past = history.loc[:issue_date].tail(window)
    level = float(past.mean()) if len(past) else 0.0
    return np.full(horizon, max(0.0, level), dtype=float)


def ets_forecast(history: pd.Series, issue_date: date, horizon: int) -> np.ndarray | None:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except Exception:
        return None
    series = history.loc[:issue_date].astype(float)
    if len(series) < 21:
        return None
    try:
        model = ExponentialSmoothing(
            series,
            seasonal_periods=7,
            trend="add",
            seasonal="add",
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True)
        fc = fit.forecast(horizon)
        return np.maximum(np.asarray(fc, dtype=float), 0.0)
    except Exception:
        return None


def ensure_synthetic_daily_in_db(config: AppConfig | None = None) -> int:
    """Materialize synthetic campus daily volume into marts if empty."""
    cfg = config or load_config()
    track = "synthetic_campus"
    df = generate_daily_arrivals(CampusScenarioSpec())
    with connect(cfg.database) as conn:
        conn.execute("DELETE FROM marts.daily_volume WHERE source_track = %s", (track,))
        rows = [
            (track, date.fromisoformat(r.arrival_date), int(r.distinct_arrivals), "synthetic_complete")
            for r in df.itertuples()
        ]
        with conn.cursor() as cur:
            with cur.copy(
                "COPY marts.daily_volume (source_track, arrival_date, distinct_arrivals, coverage_status) FROM STDIN"
            ) as copy:
                for row in rows:
                    copy.write_row(row)
        conn.commit()
    return len(rows)


def load_daily_series(source_track: str, *, config: AppConfig | None = None) -> pd.Series:
    cfg = config or load_config()
    with connect(cfg.database) as conn:
        rows = conn.execute(
            """
            SELECT arrival_date, distinct_arrivals
            FROM marts.daily_volume
            WHERE source_track = %s
            ORDER BY arrival_date
            """,
            (source_track,),
        ).fetchall()
    if not rows:
        raise ValueError(f"No daily_volume for track={source_track}")
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.Series([r[1] for r in rows], index=idx, name="arrivals")


def run_forecast_experiment(
    *,
    source_track: str = "synthetic_campus",
    horizon: int = 7,
    config: AppConfig | None = None,
) -> ForecastRunResult:
    cfg = config or load_config()
    if source_track == "synthetic_campus":
        ensure_synthetic_daily_in_db(cfg)

    series = load_daily_series(source_track, config=cfg)
    # Expanding-window folds: need warm-up of at least 28 days, then every 7 days
    start_idx = 28
    evals: list[ForecastEvalRow] = []
    fold = 0
    i = start_idx
    while i + horizon < len(series):
        issue = series.index[i - 1].date()
        actual_idx = series.index[i : i + horizon]
        y_true = series.iloc[i : i + horizon].to_numpy(dtype=float)
        hist = series.iloc[:i]

        base = seasonal_naive(hist, issue, horizon)
        ma = moving_average(hist, issue, horizon)
        ets = ets_forecast(hist, issue, horizon)

        candidates = {
            "seasonal_naive": base,
            "moving_average_14": ma,
        }
        if ets is not None:
            candidates["ets_weekly"] = ets

        for name, pred in candidates.items():
            mae = float(mean_absolute_error(y_true, pred))
            base_mae = float(mean_absolute_error(y_true, base))
            wape = _wape(y_true, pred)
            improv = None if base_mae == 0 else (base_mae - mae) / base_mae
            evals.append(
                ForecastEvalRow(
                    fold_id=f"fold_{fold:03d}",
                    issue_date=issue.isoformat(),
                    model=name,
                    mae=mae,
                    wape=wape,
                    baseline_mae=base_mae,
                    improvement_vs_baseline=improv,
                    n_days=horizon,
                )
            )
        fold += 1
        i += horizon

    # Select model by mean MAE (lower better); baseline remains eligible.
    by_model: dict[str, list[float]] = {}
    for e in evals:
        by_model.setdefault(e.model, []).append(e.mae)
    mean_mae = {m: float(np.mean(v)) for m, v in by_model.items()}
    selected = min(mean_mae, key=mean_mae.get)

    # Final next-seven from last issue date
    last_issue = series.index[-1].date()
    hist = series
    if selected == "seasonal_naive":
        pred = seasonal_naive(hist, last_issue, horizon)
    elif selected == "moving_average_14":
        pred = moving_average(hist, last_issue, horizon)
    else:
        pred = ets_forecast(hist, last_issue, horizon)
        if pred is None:
            pred = seasonal_naive(hist, last_issue, horizon)
            selected = "seasonal_naive"

    next_seven = [
        {
            "issue_date": last_issue.isoformat(),
            "target_date": (last_issue + timedelta(days=h)).isoformat(),
            "predicted_count": float(pred[h - 1]),
            "model": selected,
            "source_track": source_track,
        }
        for h in range(1, horizon + 1)
    ]

    model_version = f"forecast_{source_track}_{selected}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model_version": model_version,
        "source_track": source_track,
        "horizon_days": horizon,
        "selected_model": selected,
        "mean_mae": mean_mae,
        "evaluations": [asdict(e) for e in evals],
        "next_seven": next_seven,
    }
    (ARTIFACT_DIR / f"{model_version}.json").write_text(json.dumps(artifact, indent=2))

    # Persist to DB
    with connect(cfg.database) as conn:
        conn.execute(
            """
            INSERT INTO models.model_registry (
                model_version, model_family, source_track, feature_contract,
                dataset_snapshot_id, environment, artifact_uri, selection_status, metrics_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (model_version) DO NOTHING
            """,
            (
                model_version,
                "forecast",
                source_track,
                "daily_arrivals_v1",
                f"{source_track}:daily_volume",
                "local",
                str(ARTIFACT_DIR / f"{model_version}.json"),
                "selected",
                json.dumps({"mean_mae": mean_mae, "selected": selected}),
            ),
        )
        # demote other forecast models for this track
        conn.execute(
            """
            UPDATE models.model_registry
            SET selection_status = 'candidate'
            WHERE model_family = 'forecast' AND source_track = %s AND model_version <> %s
            """,
            (source_track, model_version),
        )
        for e in evals:
            conn.execute(
                """
                INSERT INTO models.evaluation_results (
                    model_version, fold_id, horizon_days, metric_name, metric_value, details_json
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    model_version,
                    e.fold_id,
                    horizon,
                    f"{e.model}_mae",
                    e.mae,
                    json.dumps(asdict(e)),
                ),
            )
        for row in next_seven:
            conn.execute(
                """
                INSERT INTO models.forecast_predictions (
                    model_version, source_track, issue_date, target_date, predicted_count
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (model_version, source_track, issue_date, target_date)
                DO UPDATE SET predicted_count = EXCLUDED.predicted_count
                """,
                (
                    model_version,
                    source_track,
                    row["issue_date"],
                    row["target_date"],
                    row["predicted_count"],
                ),
            )
        conn.commit()

    return ForecastRunResult(
        model_version=model_version,
        source_track=source_track,
        horizon_days=horizon,
        selected_model=selected,
        evaluations=evals,
        next_seven=next_seven,
    )
