from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from employee.models import WearableSample


@dataclass(frozen=True)
class StressWindowResult:
    stress_score: float
    risk_level: str
    signal_quality: float
    trigger_recommended: bool
    window_start: datetime
    window_end: datetime
    feature_summary: dict[str, Any]
    model_version: str = "stress-heuristic-v1"


@dataclass(frozen=True)
class FinalRiskResult:
    stress_score: float
    burnout_score: float
    final_score: float
    risk_level: str
    inference_mode: str
    confidence_level: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _risk_from_score(score: float) -> str:
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "moderate"
    return "low"


def _normalize(value: float, lower: float, upper: float) -> float:
    span = upper - lower
    if span <= 0:
        return 0.0
    return _clamp01((value - lower) / span)


def _resolve_stress_runtime_strategy() -> tuple[str, str, str]:
    requested_strategy = os.getenv("STRESS_RUNTIME_STRATEGY", "heuristic").strip().lower() or "heuristic"
    if requested_strategy == "heuristic":
        return "heuristic", requested_strategy, ""
    return "heuristic", requested_strategy, f"unsupported_runtime_strategy:{requested_strategy}"


def compute_stress_window(samples: list[WearableSample]) -> StressWindowResult:
    runtime_strategy, requested_runtime_strategy, fallback_reason = _resolve_stress_runtime_strategy()

    if not samples:
        now = datetime.utcnow()
        return StressWindowResult(
            stress_score=0.0,
            risk_level="low",
            signal_quality=0.0,
            trigger_recommended=False,
            window_start=now,
            window_end=now,
            feature_summary={
                "runtime_strategy": runtime_strategy,
                "requested_runtime_strategy": requested_runtime_strategy,
                "fallback_reason": fallback_reason,
            },
        )

    grouped: dict[str, list[float]] = defaultdict(list)
    qualities: list[float] = []
    for sample in samples:
        grouped[sample.sensor_type].append(float(sample.value))
        qualities.append(float(sample.quality))

    hr_mean = _safe_mean(grouped.get("hr", []))
    eda_mean = _safe_mean(grouped.get("eda", []))
    temp_mean = _safe_mean(grouped.get("temp", []))
    hrv_mean = _safe_mean(grouped.get("hrv", []))

    hr_component = _normalize(hr_mean, 60.0, 120.0)
    eda_component = _normalize(eda_mean, 0.2, 8.0)
    temp_component = _normalize(temp_mean, 31.0, 37.5)
    hrv_inverse_component = 1.0 - _normalize(hrv_mean, 20.0, 110.0)

    score = _clamp01(
        (0.45 * hr_component)
        + (0.30 * eda_component)
        + (0.15 * hrv_inverse_component)
        + (0.10 * temp_component)
    )

    signal_quality = _clamp01(_safe_mean(qualities) if qualities else 0.0)
    if signal_quality < 0.35:
        score = min(score, 0.55)

    window_start = min(sample.recorded_at for sample in samples)
    window_end = max(sample.recorded_at for sample in samples)
    risk_level = _risk_from_score(score)
    trigger_recommended = score >= 0.75 and signal_quality >= 0.55

    return StressWindowResult(
        stress_score=score,
        risk_level=risk_level,
        signal_quality=signal_quality,
        trigger_recommended=trigger_recommended,
        window_start=window_start,
        window_end=window_end,
        feature_summary={
            "runtime_strategy": runtime_strategy,
            "requested_runtime_strategy": requested_runtime_strategy,
            "fallback_reason": fallback_reason,
            "hr_mean": hr_mean,
            "eda_mean": eda_mean,
            "temp_mean": temp_mean,
            "hrv_mean": hrv_mean,
            "hr_component": hr_component,
            "eda_component": eda_component,
            "temp_component": temp_component,
            "hrv_inverse_component": hrv_inverse_component,
        },
    )


def compute_burnout_composite(payload: dict[str, Any]) -> tuple[float, dict[str, float]]:
    exhaustion = _normalize(float(payload["exhaustion_score"]), 1.0, 5.0)
    cynicism = _normalize(float(payload["cynicism_score"]), 1.0, 5.0)
    efficacy_inverse = 1.0 - _normalize(float(payload["efficacy_score"]), 1.0, 5.0)
    work_life_penalty = 1.0 - _normalize(float(payload["work_life_balance_score"]), 1.0, 5.0)
    support_penalty = 1.0 - _normalize(float(payload["manager_support_score"]), 1.0, 5.0)
    deadline_pressure = _normalize(float(payload["deadline_pressure_score"]), 1.0, 5.0)

    composite_score = _clamp01(
        (0.30 * exhaustion)
        + (0.20 * cynicism)
        + (0.15 * efficacy_inverse)
        + (0.15 * deadline_pressure)
        + (0.10 * support_penalty)
        + (0.10 * work_life_penalty)
    )

    factors = {
        "exhaustion": exhaustion,
        "cynicism": cynicism,
        "efficacy_inverse": efficacy_inverse,
        "work_life_penalty": work_life_penalty,
        "support_penalty": support_penalty,
        "deadline_pressure": deadline_pressure,
    }
    return composite_score, factors


def recommendation_for_risk(risk_level: str) -> str:
    if risk_level == "high":
        return "Encaminhar para avaliacao clinica e acompanhamento profissional prioritario."
    if risk_level == "moderate":
        return "Iniciar intervencao breve, acompanhamento semanal e nova avaliacao."
    return "Manter monitoramento, psicoeducacao e reavaliacao periodica."


def compute_final_risk(stress_score: float | None, burnout_score: float | None) -> FinalRiskResult:
    normalized_stress = _clamp01(stress_score) if stress_score is not None else None
    normalized_burnout = _clamp01(burnout_score) if burnout_score is not None else None

    if normalized_stress is not None and normalized_burnout is not None:
        final_score = _clamp01((0.35 * normalized_stress) + (0.65 * normalized_burnout))
        return FinalRiskResult(
            stress_score=normalized_stress,
            burnout_score=normalized_burnout,
            final_score=final_score,
            risk_level=_risk_from_score(final_score),
            inference_mode="hybrid",
            confidence_level="high",
        )

    if normalized_burnout is not None:
        return FinalRiskResult(
            stress_score=0.0,
            burnout_score=normalized_burnout,
            final_score=normalized_burnout,
            risk_level=_risk_from_score(normalized_burnout),
            inference_mode="assessment_only",
            confidence_level="moderate",
        )

    if normalized_stress is not None:
        return FinalRiskResult(
            stress_score=normalized_stress,
            burnout_score=0.0,
            final_score=normalized_stress,
            risk_level=_risk_from_score(normalized_stress),
            inference_mode="wearable_only",
            confidence_level="low",
        )

    raise ValueError("Nao foi possivel inferir risco: stress_score e burnout_score ausentes.")


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
