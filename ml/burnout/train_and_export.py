#!/usr/bin/env python3
"""Train burn-rate models and export artifacts for online inference.

Outputs:
- model_mid.joblib  (point prediction)
- model_q10.joblib  (lower quantile)
- model_q90.joblib  (upper quantile)
- metadata.json     (metrics, feature order, version)

Example:
    python burnout/employee/ml/burnout/train_and_export.py \
      --data burnout/employee/ml/burnout/employeedataset.csv \
      --out-dir artifacts/burn_rate/v6 \
      --target-strategy hybrid
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    explained_variance_score,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_pinball_loss,
    mean_squared_error,
    median_absolute_error,
    r2_score,
)
from sklearn.model_selection import RandomizedSearchCV, cross_val_score, train_test_split

FEATURE_COLUMNS = [
    "gender",
    "company_type",
    "wfh_setup_available",
    "designation",
    "resource_allocation",
    "work_hours_per_week",
    "sleep_hours",
    "team_size",
    "recognition_frequency",
    "exhaustion_score",
    "cynicism_score",
    "efficacy_score",
    "work_life_balance_score",
    "manager_support_score",
    "deadline_pressure_score",
]

CSV_TO_FEATURE = {
    "Gender": "gender",
    "Company Type": "company_type",
    "WFH Setup Available": "wfh_setup_available",
    "Designation": "designation",
    "Resource Allocation": "resource_allocation",
    "Work Hours per Week": "work_hours_per_week",
    "Sleep Hours": "sleep_hours",
    "Work-Life Balance Score": "work_life_balance_score",
    "Manager Support Score": "manager_support_score",
    "Deadline Pressure Score": "deadline_pressure_score",
    "Team Size": "team_size",
    "Recognition Frequency": "recognition_frequency",
    "Mental Fatigue Score": "mental_fatigue_score",
    "Burn Rate": "burn_rate",
}

REQUIRED_INPUT_COLUMNS = [key for key in CSV_TO_FEATURE.keys() if key != "Burn Rate"]

EXPECTED_RANGES = {
    "designation": (0, 5),
    "resource_allocation": (1.0, 10.0),
    "work_hours_per_week": (1, 120),
    "sleep_hours": (0.0, 24.0),
    "work_life_balance_score": (1, 5),
    "manager_support_score": (1, 5),
    "deadline_pressure_score": (1, 5),
    "team_size": (1, 1000),
    "recognition_frequency": (0, 1000),
    "exhaustion_score": (1.0, 5.0),
    "cynicism_score": (1.0, 5.0),
    "efficacy_score": (1.0, 5.0),
    "mental_fatigue_score": (0.0, 10.0),
    "burn_rate": (0.0, 1.0),
    "burnout_target": (0.0, 1.0),
}

SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent.parent
REPO_ROOT = APP_DIR.parent


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return REPO_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and export burn-rate models.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("employeedataset.csv"),
        help="CSV path with training data.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/burn_rate/default"),
        help="Output directory for artifacts.",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split ratio.")
    parser.add_argument("--cv", type=int, default=5, help="Cross-validation folds for CV RMSE.")
    parser.add_argument("--tune-mid", action="store_true", help="Run RandomizedSearchCV for model_mid.")
    parser.add_argument("--n-iter", type=int, default=25, help="RandomizedSearchCV iterations for model_mid.")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed.")
    parser.add_argument("--version", type=str, default="v1", help="Model version label.")
    parser.add_argument(
        "--target-strategy",
        choices=["reported", "composite", "hybrid", "sdd-v2"],
        default="sdd-v2",
        help=(
            "reported: usa somente Burn Rate do dataset; "
            "composite: ignora Burn Rate e calcula score composto legado; "
            "hybrid: media ponderada entre Burn Rate e score composto legado; "
            "sdd-v2: calcula alvo com os fatores diretos do questionario SDD v2."
        ),
    )
    return parser.parse_args()


def resolve_input_data_path(csv_path: Path) -> Path:
    repo_root = find_repo_root(SCRIPT_DIR)
    if csv_path.is_absolute() and csv_path.exists():
        return csv_path

    file_name = csv_path.name
    candidates = [
        Path.cwd() / csv_path,
        Path.cwd() / file_name,
        repo_root / csv_path,
        repo_root / file_name,
        repo_root / "TreinandoHarvardRev01" / file_name,
        APP_DIR / csv_path,
        APP_DIR / file_name,
        SCRIPT_DIR / csv_path,
        SCRIPT_DIR / file_name,
        SCRIPT_DIR / "TreinandoHarvardRev01" / file_name,
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate

    tried = "\n - ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Dataset CSV not found. Tried:\n - {tried}")


def resolve_output_dir(out_dir: Path) -> Path:
    if out_dir.is_absolute():
        return out_dir
    return APP_DIR / out_dir


def _build_composite_target(df: pd.DataFrame) -> pd.Series:
    pressure = _normalize(df["deadline_pressure_score"], 1.0, 5.0)
    work_hours = _normalize(df["work_hours_per_week"], 35.0, 65.0)
    sleep_penalty = 1.0 - _normalize(df["sleep_hours"], 5.0, 9.0)
    support_penalty = 1.0 - _normalize(df["manager_support_score"], 1.0, 5.0)
    balance_penalty = 1.0 - _normalize(df["work_life_balance_score"], 1.0, 5.0)
    allocation = _normalize(df["resource_allocation"], 1.0, 10.0)

    return (
        (0.25 * pressure)
        + (0.20 * allocation)
        + (0.20 * work_hours)
        + (0.15 * sleep_penalty)
        + (0.10 * support_penalty)
        + (0.10 * balance_penalty)
    ).clip(0.0, 1.0)


def _build_sdd_v2_target(df: pd.DataFrame) -> pd.Series:
    exhaustion = _normalize(df["exhaustion_score"], 1.0, 5.0)
    cynicism = _normalize(df["cynicism_score"], 1.0, 5.0)
    efficacy_inverse = 1.0 - _normalize(df["efficacy_score"], 1.0, 5.0)
    deadline_pressure = _normalize(df["deadline_pressure_score"], 1.0, 5.0)
    support_penalty = 1.0 - _normalize(df["manager_support_score"], 1.0, 5.0)
    work_life_penalty = 1.0 - _normalize(df["work_life_balance_score"], 1.0, 5.0)

    return (
        (0.30 * exhaustion)
        + (0.20 * cynicism)
        + (0.15 * efficacy_inverse)
        + (0.15 * deadline_pressure)
        + (0.10 * support_penalty)
        + (0.10 * work_life_penalty)
    ).clip(0.0, 1.0)


def _derive_questionnaire_proxy_features(df: pd.DataFrame) -> pd.DataFrame:
    df["exhaustion_score"] = 1.0 + (4.0 * _normalize(df["mental_fatigue_score"], 0.0, 10.0))
    df["cynicism_score"] = 1.0 + (4.0 * _normalize(df["resource_allocation"], 1.0, 10.0))

    recognition_min = float(df["recognition_frequency"].min())
    recognition_max = float(df["recognition_frequency"].max())
    if recognition_max <= recognition_min:
        recognition_min = 0.0
        recognition_max = 1.0
    df["efficacy_score"] = 1.0 + (4.0 * _normalize(df["recognition_frequency"], recognition_min, recognition_max))
    return df


def _normalize(series: pd.Series, min_value: float, max_value: float) -> pd.Series:
    span = max_value - min_value
    if span <= 0:
        return pd.Series(0.0, index=series.index)
    return ((series - min_value) / span).clip(0.0, 1.0)


def load_and_prepare_data(
    csv_path: Path, target_strategy: str
) -> tuple[pd.DataFrame, pd.Series, dict[str, int], str]:
    df = pd.read_csv(csv_path)

    missing = [col for col in REQUIRED_INPUT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in CSV: {missing}")

    df = df.rename(columns=CSV_TO_FEATURE)

    # Categorical normalization to match runtime encoding.
    gender_map = {"Female": 0, "Male": 1, "Other": 2, "0": 0, "1": 1, "2": 2}
    company_map = {"Service": 0, "Product": 1, "0": 0, "1": 1}
    wfh_map = {"Yes": 1, "No": 0, True: 1, False: 0, "1": 1, "0": 0}

    df["gender"] = df["gender"].map(gender_map)
    df["company_type"] = df["company_type"].map(company_map)
    df["wfh_setup_available"] = df["wfh_setup_available"].map(wfh_map)

    numeric_features = [col for col in FEATURE_COLUMNS if col not in {"gender", "company_type", "wfh_setup_available"}]
    source_numeric_features = numeric_features + ["mental_fatigue_score", "burn_rate"]
    for col in source_numeric_features:
        if col not in df.columns:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = _derive_questionnaire_proxy_features(df)
    composite_target = _build_composite_target(df)
    sdd_v2_target = _build_sdd_v2_target(df)
    reported_available = "burn_rate" in df.columns and df["burn_rate"].notna().any()

    if target_strategy == "reported":
        if not reported_available:
            raise ValueError("Target strategy 'reported' exige coluna Burn Rate com valores validos.")
        df["burnout_target"] = df["burn_rate"]
        target_used = "reported_burn_rate"
    elif target_strategy == "composite":
        df["burnout_target"] = composite_target
        target_used = "composite_score_v1"
    elif target_strategy == "sdd-v2":
        df["burnout_target"] = sdd_v2_target
        target_used = "burnout_composite_sdd_v2"
    else:
        if reported_available:
            df["burnout_target"] = (0.60 * composite_target) + (0.40 * df["burn_rate"])
            target_used = "hybrid_60_composite_40_reported"
        else:
            df["burnout_target"] = composite_target
            target_used = "hybrid_fallback_composite_only"

    # Keep only rows with complete supervised signal.
    used_cols = FEATURE_COLUMNS + ["burnout_target"]
    before = len(df)
    df = df.dropna(subset=used_cols).copy()
    dropped_missing = before - len(df)

    in_range_mask = pd.Series(True, index=df.index)
    for column, (minimum, maximum) in EXPECTED_RANGES.items():
        if column not in df.columns:
            continue
        in_range_mask &= df[column].between(minimum, maximum, inclusive="both")
    rows_before_ranges = len(df)
    df = df[in_range_mask].copy()
    dropped_out_of_range = rows_before_ranges - len(df)

    X = df[FEATURE_COLUMNS]
    y = df["burnout_target"]

    return (
        X,
        y,
        {
            "rows_before": before,
            "rows_dropped_missing": dropped_missing,
            "rows_dropped_out_of_range": dropped_out_of_range,
            "rows_used": len(df),
        },
        target_used,
    )


def train_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    random_state: int,
    cv: int,
    tune_mid: bool,
    n_iter: int,
) -> tuple[GradientBoostingRegressor, GradientBoostingRegressor, GradientBoostingRegressor, dict[str, Any]]:
    # Aligned with the best family observed in the notebook (GB).
    mid_base = GradientBoostingRegressor(
        loss="squared_error",
        n_estimators=300,
        learning_rate=0.03,
        max_depth=5,
        random_state=random_state,
    )
    model_q10 = GradientBoostingRegressor(
        loss="quantile",
        alpha=0.10,
        n_estimators=300,
        learning_rate=0.03,
        max_depth=5,
        random_state=random_state,
    )
    model_q90 = GradientBoostingRegressor(
        loss="quantile",
        alpha=0.90,
        n_estimators=300,
        learning_rate=0.03,
        max_depth=5,
        random_state=random_state,
    )

    training_info: dict[str, Any] = {
        "model_family": "GradientBoostingRegressor",
        "mid_search": "fit",
        "mid_best_params": {},
    }
    if tune_mid:
        search = RandomizedSearchCV(
            estimator=mid_base,
            param_distributions={
                "n_estimators": [150, 250, 300, 400, 500],
                "learning_rate": [0.01, 0.02, 0.03, 0.05, 0.08, 0.1],
                "max_depth": [2, 3, 4, 5, 6],
                "min_samples_leaf": [1, 2, 5, 10, 20],
                "subsample": [0.7, 0.8, 0.9, 1.0],
            },
            n_iter=n_iter,
            scoring="neg_root_mean_squared_error",
            cv=cv,
            random_state=random_state,
            n_jobs=-1,
            verbose=0,
        )
        search.fit(X_train, y_train)
        model_mid = search.best_estimator_
        training_info["mid_search"] = "RandomizedSearchCV"
        training_info["mid_best_params"] = search.best_params_
        training_info["mid_cv_rmse_best"] = float(-search.best_score_)
    else:
        model_mid = mid_base.fit(X_train, y_train)

    model_q10.fit(X_train, y_train)
    model_q90.fit(X_train, y_train)

    return model_mid, model_q10, model_q90, training_info


def evaluate(
    model_mid,
    model_q10,
    model_q90,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    cv: int,
) -> dict[str, float]:
    pred_mid = model_mid.predict(X_test)
    pred_q10 = model_q10.predict(X_test)
    pred_q90 = model_q90.predict(X_test)
    baseline_pred = [float(y_train.mean())] * len(y_test)

    mae = mean_absolute_error(y_test, pred_mid)
    rmse = mean_squared_error(y_test, pred_mid) ** 0.5
    r2 = r2_score(y_test, pred_mid)
    medae = median_absolute_error(y_test, pred_mid)
    evs = explained_variance_score(y_test, pred_mid)
    y_test_nonzero_mask = y_test.abs() > 1e-6
    if bool(y_test_nonzero_mask.any()):
        mape_nonzero = float(mean_absolute_percentage_error(y_test[y_test_nonzero_mask], pred_mid[y_test_nonzero_mask]))
    else:
        mape_nonzero = float("nan")
    baseline_rmse = math.sqrt(mean_squared_error(y_test, baseline_pred))
    baseline_mae = mean_absolute_error(y_test, baseline_pred)
    improvement_vs_baseline_rmse_pct = ((baseline_rmse - rmse) / baseline_rmse * 100.0) if baseline_rmse else 0.0

    pinball_q10 = mean_pinball_loss(y_test, pred_q10, alpha=0.10)
    pinball_q90 = mean_pinball_loss(y_test, pred_q90, alpha=0.90)

    coverage = ((y_test >= pred_q10) & (y_test <= pred_q90)).mean()
    cv_scores = cross_val_score(
        model_mid,
        X_train,
        y_train,
        scoring="neg_root_mean_squared_error",
        cv=cv,
        n_jobs=-1,
    )
    cv_rmse_mean = float((-cv_scores).mean())
    cv_rmse_std = float((-cv_scores).std())

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "medae": float(medae),
        "explained_variance": float(evs),
        "mape_nonzero": mape_nonzero,
        "baseline_rmse_mean": float(baseline_rmse),
        "baseline_mae_mean": float(baseline_mae),
        "improvement_vs_baseline_rmse_pct": float(improvement_vs_baseline_rmse_pct),
        "cv_rmse_mean": cv_rmse_mean,
        "cv_rmse_std": cv_rmse_std,
        "pinball_q10": float(pinball_q10),
        "pinball_q90": float(pinball_q90),
        "interval_coverage": float(coverage),
    }


def export_artifacts(
    out_dir: Path,
    model_mid,
    model_q10,
    model_q90,
    metrics: dict[str, float],
    data_stats: dict[str, int],
    version: str,
    target_used: str,
    feature_stats: dict[str, dict[str, float]],
    training_info: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    mid_path = out_dir / "model_mid.joblib"
    q10_path = out_dir / "model_q10.joblib"
    q90_path = out_dir / "model_q90.joblib"
    metadata_path = out_dir / "metadata.json"

    joblib.dump(model_mid, mid_path)
    joblib.dump(model_q10, q10_path)
    joblib.dump(model_q90, q90_path)

    previous_report = compare_with_previous_version(out_dir, metrics)

    metadata = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_order": FEATURE_COLUMNS,
        "target": target_used,
        "artifacts": {
            "model_mid": str(mid_path.resolve()),
            "model_q10": str(q10_path.resolve()),
            "model_q90": str(q90_path.resolve()),
        },
        "metrics": metrics,
        "baseline": {
            "note": "Baseline predictor uses train mean target.",
            "rmse": metrics["baseline_rmse_mean"],
            "mae": metrics["baseline_mae_mean"],
        },
        "model_selection": training_info,
        "feature_stats": feature_stats,
        "comparison_to_previous_version": previous_report,
        "data_stats": data_stats,
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def export_feature_importance(
    out_dir: Path,
    model_mid,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    random_state: int,
) -> None:
    importance_path = out_dir / "feature_importance.csv"
    chart_path = out_dir / "feature_importance.png"

    # Prefer model-native importance when available; fallback to permutation.
    if hasattr(model_mid, "feature_importances_"):
        importances = model_mid.feature_importances_
    else:
        perm = permutation_importance(
            model_mid,
            X_test,
            y_test,
            n_repeats=20,
            random_state=random_state,
            scoring="neg_root_mean_squared_error",
        )
        importances = perm.importances_mean

    fi = (
        pd.DataFrame({"feature": X_test.columns, "importance": importances})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    fi.to_csv(importance_path, index=False)

    # Horizontal chart from most to least important (optional dependency).
    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(fi["feature"][::-1], fi["importance"][::-1], color="#3f7fdb")
        ax.set_title("Feature Importance - Winner Model (model_mid)")
        ax.set_xlabel("Importance")
        ax.set_ylabel("Feature")
        fig.tight_layout()
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
    except Exception:
        # Keep training/export healthy even when matplotlib is not installed.
        pass


def build_feature_stats(X: pd.DataFrame) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for feature in X.columns:
        col = pd.to_numeric(X[feature], errors="coerce")
        stats[feature] = {
            "min": float(col.min()),
            "max": float(col.max()),
            "mean": float(col.mean()),
            "std": float(col.std(ddof=0)) if float(col.std(ddof=0)) > 0 else 0.0,
        }
    return stats


def compare_with_previous_version(out_dir: Path, current_metrics: dict[str, float]) -> dict[str, Any]:
    parent = out_dir.parent
    previous_candidates = []
    for item in parent.iterdir():
        if not item.is_dir() or item == out_dir:
            continue
        metadata_file = item / "metadata.json"
        if metadata_file.exists():
            previous_candidates.append(metadata_file)

    if not previous_candidates:
        return {"status": "no_previous_version_found"}

    latest_metadata = max(previous_candidates, key=lambda p: p.stat().st_mtime)
    try:
        previous = json.loads(latest_metadata.read_text(encoding="utf-8"))
        prev_metrics = previous.get("metrics", {})
        prev_rmse = float(prev_metrics.get("rmse"))
        prev_mae = float(prev_metrics.get("mae"))
        prev_r2 = float(prev_metrics.get("r2"))
    except Exception:
        return {"status": "previous_metadata_unreadable", "path": str(latest_metadata)}

    return {
        "status": "compared",
        "previous_version": previous.get("version", latest_metadata.parent.name),
        "previous_metadata_path": str(latest_metadata),
        "delta_rmse": float(current_metrics["rmse"] - prev_rmse),
        "delta_mae": float(current_metrics["mae"] - prev_mae),
        "delta_r2": float(current_metrics["r2"] - prev_r2),
        "improved_rmse": current_metrics["rmse"] < prev_rmse,
        "improved_mae": current_metrics["mae"] < prev_mae,
        "improved_r2": current_metrics["r2"] > prev_r2,
    }


def main() -> None:
    args = parse_args()
    data_path = resolve_input_data_path(args.data)
    output_dir = resolve_output_dir(args.out_dir)

    X, y, data_stats, target_used = load_and_prepare_data(data_path, args.target_strategy)

    if len(X) < 100:
        raise ValueError(f"Not enough rows after cleaning ({len(X)}). Need at least 100 rows.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    model_mid, model_q10, model_q90, training_info = train_models(
        X_train, y_train, args.random_state, args.cv, args.tune_mid, args.n_iter
    )
    metrics = evaluate(model_mid, model_q10, model_q90, X_train, y_train, X_test, y_test, args.cv)
    feature_stats = build_feature_stats(X_train)
    export_artifacts(
        output_dir,
        model_mid,
        model_q10,
        model_q90,
        metrics,
        data_stats,
        args.version,
        target_used,
        feature_stats,
        training_info,
    )
    export_feature_importance(output_dir, model_mid, X_test, y_test, args.random_state)

    print("Training complete")
    print(f"Rows used: {data_stats['rows_used']}")
    print(f"Rows dropped (missing): {data_stats['rows_dropped_missing']}")
    print(f"Rows dropped (out of range): {data_stats['rows_dropped_out_of_range']}")
    print(f"CV RMSE (mean +- std): {metrics['cv_rmse_mean']:.6f} +- {metrics['cv_rmse_std']:.6f}")
    print(f"RMSE: {metrics['rmse']:.6f}")
    print(f"MAE: {metrics['mae']:.6f}")
    print(f"MedAE: {metrics['medae']:.6f}")
    print(f"MAPE (non-zero target): {metrics['mape_nonzero']:.6f}")
    print(f"R2: {metrics['r2']:.6f}")
    print(f"Explained Variance: {metrics['explained_variance']:.6f}")
    print(f"Baseline RMSE: {metrics['baseline_rmse_mean']:.6f}")
    print(f"RMSE Improvement vs Baseline: {metrics['improvement_vs_baseline_rmse_pct']:.2f}%")
    print(f"Coverage (q10-q90): {metrics['interval_coverage']:.4f}")
    print(f"Target strategy used: {target_used}")
    print(f"Dataset: {data_path}")
    print(f"Feature importance CSV: {(output_dir / 'feature_importance.csv').resolve()}")
    print(f"Feature importance chart: {(output_dir / 'feature_importance.png').resolve()}")
    print(f"Artifacts saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
