"""SLA-risk experiment with leakage controls (Phase 8).

Polarity of `made_sla` remains unresolved per Phase 0. This module trains a
*source-flag prediction* experiment (predict latest-observed made_sla from
opening-time allowlisted features) and documents that it is NOT a verified
breach classifier until polarity is closed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from itintel.config import ROOT, AppConfig, load_config
from itintel.db.connection import connect

ARTIFACT_DIR = ROOT / "data" / "processed" / "models"

FEATURE_COLS_CAT = [
    "impact",
    "urgency",
    "priority",
    "category",
    "contact_type",
    "initial_assignment_group",
]
FEATURE_COLS_NUM = ["open_weekday", "open_hour"]
PROHIBITED = {
    "resolved_at",
    "closed_at",
    "closed_code",
    "resolved_by",
    "latest_state",
    "made_sla",
    "reopen_count",
    "reassignment_count",
}


@dataclass
class SlaRunResult:
    model_version: str
    status: str
    label_name: str
    polarity_status: str
    n_rows: int
    prevalence: float | None
    average_precision: float | None
    threshold: float | None
    test_precision: float | None
    test_recall: float | None
    notes: str


def _load_frame(source_track: str, config: AppConfig) -> pd.DataFrame:
    with connect(config.database) as conn:
        rows = conn.execute(
            """
            SELECT
                f.incident_number,
                f.opened_at,
                f.latest_made_sla,
                o.open_weekday,
                o.open_hour,
                o.impact,
                o.urgency,
                o.priority,
                o.category,
                o.contact_type,
                o.initial_assignment_group,
                o.eligible
            FROM marts.ticket_open_features o
            JOIN marts.fact_tickets f
              ON f.source_track = o.source_track
             AND f.incident_number = o.incident_number
            WHERE o.source_track = %s
              AND o.eligible = TRUE
              AND f.latest_made_sla IS NOT NULL
            """,
            (source_track,),
        ).fetchall()
    cols = [
        "incident_number",
        "opened_at",
        "latest_made_sla",
        "open_weekday",
        "open_hour",
        "impact",
        "urgency",
        "priority",
        "category",
        "contact_type",
        "initial_assignment_group",
        "eligible",
    ]
    return pd.DataFrame(rows, columns=cols)


def run_sla_experiment(
    *,
    source_track: str = "public_historical",
    config: AppConfig | None = None,
    force: bool = False,
) -> SlaRunResult:
    cfg = config or load_config()
    polarity = "unresolved"
    label_name = "latest_observed_made_sla_source_flag"

    if not cfg.sla_enabled and not force:
        # Still allow a documented source-flag experiment when forced via CLI;
        # default config keeps resume wording gated.
        pass

    df = _load_frame(source_track, cfg)
    if df.empty:
        return SlaRunResult(
            model_version="",
            status="blocked_no_rows",
            label_name=label_name,
            polarity_status=polarity,
            n_rows=0,
            prevalence=None,
            average_precision=None,
            threshold=None,
            test_precision=None,
            test_recall=None,
            notes="No eligible opening-feature rows with non-null latest_made_sla.",
        )

    df = df.sort_values("opened_at")
    y = df["latest_made_sla"].astype(int).to_numpy()
    X = df[FEATURE_COLS_NUM + FEATURE_COLS_CAT].copy()
    for c in FEATURE_COLS_CAT:
        X[c] = X[c].fillna("UNKNOWN").astype(str)

    # Chronological split by incident opening time (no shuffle).
    n = len(df)
    train_end = int(n * 0.6)
    val_end = int(n * 0.8)
    X_train, y_train = X.iloc[:train_end], y[:train_end]
    X_val, y_val = X.iloc[train_end:val_end], y[train_end:val_end]
    X_test, y_test = X.iloc[val_end:], y[val_end:]

    pre = ColumnTransformer(
        [
            (
                "num",
                SimpleImputer(strategy="median"),
                FEATURE_COLS_NUM,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "oh",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                FEATURE_COLS_CAT,
            ),
        ]
    )

    # Baselines
    dummy = Pipeline(
        [
            ("pre", pre),
            ("clf", DummyClassifier(strategy="prior")),
        ]
    )
    dummy.fit(X_train, y_train)

    logit = Pipeline(
        [
            ("pre", pre),
            (
                "clf",
                LogisticRegression(max_iter=1000, class_weight="balanced"),
            ),
        ]
    )
    logit.fit(X_train, y_train)

    val_scores = logit.predict_proba(X_val)[:, 1]
    ap_val = float(average_precision_score(y_val, val_scores)) if len(np.unique(y_val)) > 1 else None

    # Choose threshold for precision target 0.6 on validation (if achievable).
    precision_target = 0.6
    threshold = 0.5
    test_precision = test_recall = None
    if len(np.unique(y_val)) > 1:
        prec, rec, thr = precision_recall_curve(y_val, val_scores)
        # precision_recall_curve returns thr shorter by 1
        chosen = None
        for p, t in zip(prec[:-1], thr, strict=False):
            if p >= precision_target:
                chosen = float(t)
                break
        if chosen is not None:
            threshold = chosen

    test_scores = logit.predict_proba(X_test)[:, 1]
    ap_test = (
        float(average_precision_score(y_test, test_scores)) if len(np.unique(y_test)) > 1 else None
    )
    y_hat = (test_scores >= threshold).astype(int)
    if y_hat.sum() > 0:
        test_precision = float(((y_hat == 1) & (y_test == 1)).sum() / y_hat.sum())
        test_recall = float(((y_hat == 1) & (y_test == 1)).sum() / max(1, (y_test == 1).sum()))
    else:
        test_precision = None
        test_recall = 0.0

    prevalence = float(y.mean())
    model_version = (
        f"sla_sourceflag_{source_track}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACT_DIR / f"{model_version}.joblib"
    meta_path = ARTIFACT_DIR / f"{model_version}.json"
    joblib.dump({"model": logit, "threshold": threshold, "features": FEATURE_COLS_NUM + FEATURE_COLS_CAT}, artifact_path)
    meta = {
        "model_version": model_version,
        "label_name": label_name,
        "polarity_status": polarity,
        "claim": (
            "Predicts latest-observed made_sla source flag from opening-time features. "
            "NOT a verified SLA-breach classifier."
        ),
        "prohibited_features": sorted(PROHIBITED),
        "n_rows": int(n),
        "prevalence": prevalence,
        "ap_validation": ap_val,
        "ap_test": ap_test,
        "threshold": threshold,
        "precision_target": precision_target,
        "test_precision": test_precision,
        "test_recall": test_recall,
        "dummy_train_score": float(dummy.score(X_train, y_train)),
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    # Score eligible open-ish tickets for demonstration queue (latest 500)
    demo = df.tail(500).copy()
    demo_scores = logit.predict_proba(demo[FEATURE_COLS_NUM + FEATURE_COLS_CAT])[:, 1]

    with connect(cfg.database) as conn:
        conn.execute(
            """
            INSERT INTO models.model_registry (
                model_version, model_family, source_track, feature_contract,
                dataset_snapshot_id, environment, artifact_uri, selection_status, metrics_json
            ) VALUES (%s, 'sla_source_flag', %s, 'opening_allowlist_v1', %s, 'local', %s,
                      'candidate_documented_not_breach', %s::jsonb)
            ON CONFLICT (model_version) DO NOTHING
            """,
            (
                model_version,
                source_track,
                f"{source_track}:open_features",
                str(artifact_path),
                json.dumps(meta),
            ),
        )
        conn.execute(
            """
            INSERT INTO models.evaluation_results (
                model_version, fold_id, horizon_days, metric_name, metric_value, details_json
            ) VALUES (%s, 'final_test', NULL, 'average_precision', %s, %s::jsonb)
            """,
            (model_version, ap_test, json.dumps(meta)),
        )
        for inc, cutoff, score in zip(
            demo["incident_number"], demo["opened_at"], demo_scores, strict=False
        ):
            conn.execute(
                """
                INSERT INTO models.sla_risk_predictions (
                    model_version, source_track, incident_number, feature_cutoff,
                    score, threshold, compatible
                ) VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (model_version, source_track, incident_number, feature_cutoff)
                DO UPDATE SET score = EXCLUDED.score, threshold = EXCLUDED.threshold
                """,
                (model_version, source_track, inc, cutoff, float(score), threshold),
            )
        conn.commit()

    return SlaRunResult(
        model_version=model_version,
        status="completed_source_flag_only",
        label_name=label_name,
        polarity_status=polarity,
        n_rows=int(n),
        prevalence=prevalence,
        average_precision=ap_test,
        threshold=threshold,
        test_precision=test_precision,
        test_recall=test_recall,
        notes=(
            "Do not resume-claim as SLA-breach modeling until polarity ADR closes. "
            f"AP(test)={ap_test}; prevalence={prevalence:.3f}."
        ),
    )
