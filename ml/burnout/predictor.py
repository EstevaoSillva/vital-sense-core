import os
import pickle
from pathlib import Path
from typing import Any

DEFAULT_FEATURES = (
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
)


class BurnRatePredictor:
    def __init__(self) -> None:
        self.model_version = os.getenv("BURN_RATE_MODEL_VERSION", "burnout-composite-v2-harvard")
        self.rmse = self._resolve_rmse(self.model_version)
        self.metadata = self._load_metadata(self.model_version)
        features = os.getenv("BURN_RATE_FEATURES", "")
        env_feature_order = tuple(part.strip() for part in features.split(",") if part.strip())
        metadata_feature_order = tuple(self.metadata.get("feature_order", ())) if isinstance(self.metadata, dict) else ()
        self.feature_order = env_feature_order or metadata_feature_order or DEFAULT_FEATURES
        self.feature_stats = self.metadata.get("feature_stats", {}) if isinstance(self.metadata, dict) else {}

        model_paths = self._resolve_model_paths(self.model_version)
        self.model_mid = self._load_model(model_paths["mid"])
        self.model_q10 = self._load_model(model_paths["q10"])
        self.model_q90 = self._load_model(model_paths["q90"])

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        vector = self._build_vector(payload)
        model_version = self.model_version
        prediction_source = "model"
        fallback_reason = ""

        pred = self._predict_model(self.model_mid, vector)
        q10 = self._predict_model(self.model_q10, vector)
        q90 = self._predict_model(self.model_q90, vector)

        if pred is None:
            pred = self._heuristic_prediction(payload)
            model_version = "burnout-composite-v2-heuristic"
            prediction_source = "heuristic_fallback"
            fallback_reason = "model_unavailable_or_invalid"

        if q10 is None or q90 is None:
            q10 = pred - (1.96 * self.rmse)
            q90 = pred + (1.96 * self.rmse)

        pred = _clamp01(pred)
        lower = _clamp01(min(q10, q90))
        upper = _clamp01(max(q10, q90))

        if pred < lower:
            lower = pred
        if pred > upper:
            upper = pred

        out_of_distribution, ood_features = self._assess_ood(payload)
        top_factors = self._top_factors(payload)

        return {
            "burn_rate_pred": round(pred, 4),
            "burn_rate_min": round(lower, 4),
            "burn_rate_max": round(upper, 4),
            "risk": _risk_level(pred),
            "model_version": model_version,
            "prediction_source": prediction_source,
            "out_of_distribution": out_of_distribution,
            "ood_features": ood_features,
            "top_factors": top_factors,
            "fallback_reason": fallback_reason,
        }

    def _build_vector(self, payload: dict[str, Any]) -> list[float]:
        values: list[float] = []
        for feature in self.feature_order:
            raw = payload.get(feature)
            if feature == "gender":
                values.append(float(_encode_gender(raw)))
            elif feature == "company_type":
                values.append(float(_encode_company_type(raw)))
            elif feature == "wfh_setup_available":
                values.append(1.0 if bool(raw) else 0.0)
            else:
                values.append(float(raw))
        return values

    def _predict_model(self, model: Any, vector: list[float]) -> float | None:
        if model is None:
            return None

        if hasattr(model, "predict"):
            payload: Any = [vector]
            if hasattr(model, "feature_names_in_"):
                try:
                    import pandas as pd  # type: ignore

                    payload = pd.DataFrame([vector], columns=self.feature_order)
                except Exception:
                    payload = [vector]
            try:
                result = model.predict(payload)
            except Exception:
                return None
            if result is None:
                return None
            return float(result[0])

        if callable(model):
            return float(model(vector))

        return None

    def _heuristic_prediction(self, payload: dict[str, Any]) -> float:
        exhaustion = _normalize(float(payload["exhaustion_score"]), 1.0, 5.0)
        cynicism = _normalize(float(payload["cynicism_score"]), 1.0, 5.0)
        efficacy_inverse = 1.0 - _normalize(float(payload["efficacy_score"]), 1.0, 5.0)
        pressure = _normalize(float(payload["deadline_pressure_score"]), 1.0, 5.0)
        support_penalty = 1.0 - _normalize(float(payload["manager_support_score"]), 1.0, 5.0)
        balance_penalty = 1.0 - _normalize(float(payload["work_life_balance_score"]), 1.0, 5.0)

        score = (
            (0.30 * exhaustion)
            + (0.20 * cynicism)
            + (0.15 * efficacy_inverse)
            + (0.15 * pressure)
            + (0.10 * support_penalty)
            + (0.10 * balance_penalty)
        )
        return _clamp01(score)

    @staticmethod
    def _load_model(model_path: str) -> Any:
        if not model_path:
            return None

        path = Path(model_path)
        if not path.exists() or not path.is_file():
            return None

        if path.suffix == ".joblib":
            try:
                import joblib  # type: ignore

                return joblib.load(path)
            except Exception:
                return None

        try:
            with path.open("rb") as file_handle:
                return pickle.load(file_handle)
        except Exception:
            return None

    def _resolve_model_paths(self, version: str) -> dict[str, str]:
        # Explicit env vars still work as manual override.
        explicit_mid = os.getenv("BURN_RATE_MODEL_PATH", "").strip()
        explicit_q10 = os.getenv("BURN_RATE_Q10_MODEL_PATH", "").strip()
        explicit_q90 = os.getenv("BURN_RATE_Q90_MODEL_PATH", "").strip()
        if explicit_mid and explicit_q10 and explicit_q90:
            return {"mid": explicit_mid, "q10": explicit_q10, "q90": explicit_q90}

        # Auto path by version:
        # <app_root>/artifacts/burn_rate/<version>/model_*.joblib
        base_dir = self._resolve_artifacts_base_dir()
        version_dir = base_dir / version

        return {
            "mid": str(version_dir / "model_mid.joblib"),
            "q10": str(version_dir / "model_q10.joblib"),
            "q90": str(version_dir / "model_q90.joblib"),
        }

    def _resolve_artifacts_base_dir(self) -> Path:
        app_root = Path(__file__).resolve().parents[2]
        return Path(os.getenv("BURN_RATE_ARTIFACTS_BASE_DIR", str(app_root / "artifacts" / "burn_rate")))

    def _resolve_rmse(self, version: str) -> float:
        # Manual override still supported.
        explicit_rmse = os.getenv("BURN_RATE_RMSE", "").strip()
        if explicit_rmse:
            try:
                return float(explicit_rmse)
            except ValueError:
                pass

        metadata_path = self._resolve_artifacts_base_dir() / version / "metadata.json"
        try:
            import json

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            return float(metadata.get("metrics", {}).get("rmse", 0.12))
        except Exception:
            return 0.12

    def _load_metadata(self, version: str) -> dict[str, Any]:
        metadata_path = self._resolve_artifacts_base_dir() / version / "metadata.json"
        try:
            import json

            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _assess_ood(self, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        ood_features: list[str] = []
        for feature, stats in self.feature_stats.items():
            if feature not in payload:
                continue
            try:
                value = float(payload[feature])
            except Exception:
                continue
            minimum = stats.get("min")
            maximum = stats.get("max")
            if minimum is None or maximum is None:
                continue
            if value < float(minimum) or value > float(maximum):
                ood_features.append(feature)
        return (len(ood_features) > 0, ood_features)

    def _top_factors(self, payload: dict[str, Any], top_k: int = 3) -> list[dict[str, float | str]]:
        if not hasattr(self.model_mid, "feature_importances_"):
            return []
        factors = []
        importances = list(getattr(self.model_mid, "feature_importances_", []))
        for idx, feature in enumerate(self.feature_order):
            if idx >= len(importances):
                continue
            stats = self.feature_stats.get(feature, {})
            value = _feature_numeric_value(feature, payload.get(feature, 0))
            mean = float(stats.get("mean", value))
            std = float(stats.get("std", 0.0))
            z_abs = abs((value - mean) / std) if std > 0 else 0.0
            score = float(importances[idx]) * (1.0 + z_abs)
            factors.append(
                {
                    "feature": feature,
                    "value": value,
                    "importance": float(importances[idx]),
                    "relative_impact": score,
                }
            )

        factors.sort(key=lambda item: float(item["relative_impact"]), reverse=True)
        return factors[:top_k]


def _encode_gender(value: Any) -> int:
    cleaned = str(value).strip().lower()
    mapping = {
        "0": 0,
        "female": 0,
        "1": 1,
        "male": 1,
        "2": 2,
        "other": 2,
    }
    if cleaned not in mapping:
        raise ValueError("Invalid gender. Use female/male/other or 0/1/2.")
    return mapping[cleaned]


def _encode_company_type(value: Any) -> int:
    cleaned = str(value).strip().lower()
    mapping = {
        "0": 0,
        "service": 0,
        "1": 1,
        "product": 1,
    }
    if cleaned not in mapping:
        raise ValueError("Invalid company_type. Use service/product or 0/1.")
    return mapping[cleaned]


def _feature_numeric_value(feature: str, value: Any) -> float:
    if feature == "gender":
        return float(_encode_gender(value))
    if feature == "company_type":
        return float(_encode_company_type(value))
    if feature == "wfh_setup_available":
        return 1.0 if bool(value) else 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.0
    return _clamp01((float(value) - min_value) / (max_value - min_value))


def _risk_level(pred: float) -> str:
    moderate_threshold = _env_float("BURN_RATE_RISK_MODERATE_THRESHOLD", 0.45)
    high_threshold = _env_float("BURN_RATE_RISK_HIGH_THRESHOLD", 0.70)

    moderate_threshold = _clamp01(moderate_threshold)
    high_threshold = max(moderate_threshold, _clamp01(high_threshold))

    if pred < moderate_threshold:
        return "low"
    if pred < high_threshold:
        return "moderate"
    return "high"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)
