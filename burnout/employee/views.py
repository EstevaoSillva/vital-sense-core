from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from ml.burnout.predictor import BurnRatePredictor
from .filters import EmployeeRecordFilter
from .models import (
    BurnoutAssessment,
    EmployeeRecord,
    RiskTriageDecision,
    StressInferenceSnapshot,
    WearableSample,
)
from .serializers import (
    AssessmentQuestionOutputSerializer,
    BurnoutAssessmentInputSerializer,
    BurnoutAssessmentOutputSerializer,
    DashboardSnapshotOutputSerializer,
    EmployeeAuthOutputSerializer,
    EmployeeLoginSerializer,
    BurnRatePredictionInputSerializer,
    BurnRatePredictionOutputSerializer,
    EmployeeRecordSerializer,
    RiskInferenceInputSerializer,
    RiskInferenceOutputSerializer,
    WearableIngestionOutputSerializer,
    WearableIngestionSerializer,
)
from .services.risk_pipeline import (
    compute_burnout_composite,
    compute_final_risk,
    compute_stress_window,
    recommendation_for_risk,
)


burn_rate_predictor = BurnRatePredictor()


ASSESSMENT_PROFILE_FIELD_IDS = {
    "gender",
    "company_type",
    "wfh_setup_available",
    "designation",
    "team_size",
}

BURNOUT_ASSESSMENT_QUESTIONS = [
    {
        "id": "gender",
        "category": "contexto",
        "text": "Genero",
        "input_type": "choice",
        "options": [
            {"value": "female", "label": "Feminino"},
            {"value": "male", "label": "Masculino"},
            {"value": "other", "label": "Outro"},
        ],
        "required": True,
    },
    {
        "id": "company_type",
        "category": "contexto",
        "text": "Tipo de empresa",
        "input_type": "choice",
        "options": [
            {"value": "service", "label": "Servico"},
            {"value": "product", "label": "Produto"},
        ],
        "required": True,
    },
    {
        "id": "wfh_setup_available",
        "category": "contexto",
        "text": "Voce possui estrutura adequada para trabalho remoto?",
        "input_type": "boolean",
        "options": [{"value": "true", "label": "Sim"}, {"value": "false", "label": "Nao"}],
        "required": True,
    },
    {
        "id": "designation",
        "category": "contexto",
        "text": "Nivel do cargo",
        "input_type": "choice",
        "options": [
            {"value": "0", "label": "Trainee"},
            {"value": "1", "label": "Junior"},
            {"value": "2", "label": "Pleno"},
            {"value": "3", "label": "Senior"},
            {"value": "4", "label": "Especialista"},
            {"value": "5", "label": "Executivo"},
        ],
        "required": True,
    },
    {
        "id": "resource_allocation",
        "category": "trabalho",
        "text": "Carga de trabalho atual",
        "input_type": "scale",
        "scale_labels": ["Muito baixa", "Baixa", "Moderada", "Alta", "Muito alta"],
        "min_value": 1,
        "max_value": 10,
        "required": True,
    },
    {
        "id": "work_hours_per_week",
        "category": "trabalho",
        "text": "Horas trabalhadas por semana",
        "input_type": "integer",
        "min_value": 1,
        "max_value": 120,
        "required": True,
    },
    {
        "id": "sleep_hours",
        "category": "saude",
        "text": "Horas medias de sono por dia",
        "input_type": "float",
        "min_value": 0,
        "max_value": 24,
        "required": True,
    },
    {
        "id": "team_size",
        "category": "trabalho",
        "text": "Quantidade de pessoas no time",
        "input_type": "integer",
        "min_value": 1,
        "max_value": 1000,
        "required": True,
    },
    {
        "id": "recognition_frequency",
        "category": "trabalho",
        "text": "Quantas vezes voce recebeu reconhecimento recentemente?",
        "input_type": "integer",
        "min_value": 0,
        "max_value": 1000,
        "required": True,
    },
    {
        "id": "exhaustion_score",
        "category": "burnout",
        "text": "Sinto-me emocionalmente esgotado pelo trabalho",
        "input_type": "scale",
        "scale_labels": ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"],
        "min_value": 1,
        "max_value": 5,
        "required": True,
    },
    {
        "id": "cynicism_score",
        "category": "burnout",
        "text": "Tenho me sentido distante ou cinico em relacao ao trabalho",
        "input_type": "scale",
        "scale_labels": ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"],
        "min_value": 1,
        "max_value": 5,
        "required": True,
    },
    {
        "id": "efficacy_score",
        "category": "burnout",
        "text": "Sinto que consigo realizar bem minhas atividades",
        "input_type": "scale",
        "scale_labels": ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"],
        "min_value": 1,
        "max_value": 5,
        "required": True,
    },
    {
        "id": "work_life_balance_score",
        "category": "rotina",
        "text": "Meu equilibrio entre trabalho e vida pessoal esta adequado",
        "input_type": "scale",
        "scale_labels": ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"],
        "min_value": 1,
        "max_value": 5,
        "required": True,
    },
    {
        "id": "manager_support_score",
        "category": "rotina",
        "text": "Recebo suporte suficiente da minha lideranca",
        "input_type": "scale",
        "scale_labels": ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"],
        "min_value": 1,
        "max_value": 5,
        "required": True,
    },
    {
        "id": "deadline_pressure_score",
        "category": "rotina",
        "text": "A pressao por prazos tem sido alta",
        "input_type": "scale",
        "scale_labels": ["Discordo totalmente", "Discordo", "Neutro", "Concordo", "Concordo totalmente"],
        "min_value": 1,
        "max_value": 5,
        "required": True,
    },
]


def get_authenticated_employee(user):
    employee = getattr(user, "employee_record", None)
    if employee is None:
        raise PermissionDenied("Usuario autenticado nao vinculado a employee.")
    return employee


class EmployeeRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    queryset = EmployeeRecord.objects.select_related("user", "enterprise").all().order_by("id")
    serializer_class = EmployeeRecordSerializer
    filterset_class = EmployeeRecordFilter
    search_fields = ("=id", "user__username", "user__email", "user__name", "enterprise__name", "enterprise__code")
    ordering_fields = (
        "id",
        "user__username",
        "user__email",
        "user__name",
        "enterprise__name",
        "active",
        "created_at",
        "modified_at",
    )
    ordering = ("id",)


class EmployeeLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = EmployeeLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        output = EmployeeAuthOutputSerializer(EmployeeAuthOutputSerializer.from_user(user))
        return Response(output.data, status=status.HTTP_200_OK)


class BurnRatePredictAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = BurnRatePredictionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            prediction = burn_rate_predictor.predict(serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        output = BurnRatePredictionOutputSerializer(prediction)
        return Response(output.data, status=status.HTTP_200_OK)


class WearableEventsIngestAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = WearableIngestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        employee = get_authenticated_employee(request.user)
        samples = [
            WearableSample(
                employee=employee,
                device_id=payload["device_id"],
                sensor_type=sample["sensor_type"],
                recorded_at=sample["recorded_at"],
                value=sample["value"],
                unit=sample.get("unit", ""),
                quality=sample.get("quality", 1.0),
                payload=sample.get("payload", {}),
            )
            for sample in payload["samples"]
        ]
        WearableSample.objects.bulk_create(samples)

        stress_result = compute_stress_window(samples)
        StressInferenceSnapshot.objects.create(
            employee=employee,
            window_start=stress_result.window_start,
            window_end=stress_result.window_end,
            stress_score=stress_result.stress_score,
            risk_level=stress_result.risk_level,
            signal_quality=stress_result.signal_quality,
            model_version=stress_result.model_version,
            feature_summary=stress_result.feature_summary,
            trigger_recommended=stress_result.trigger_recommended,
        )

        output = WearableIngestionOutputSerializer(
            {
                "employee_record_id": employee.id,
                "ingested_samples": len(samples),
                "stress_score": round(stress_result.stress_score, 4),
                "stress_risk": stress_result.risk_level,
                "trigger_recommended": stress_result.trigger_recommended,
                "window_start": stress_result.window_start,
                "window_end": stress_result.window_end,
                "signal_quality": round(stress_result.signal_quality, 4),
                "model_version": stress_result.model_version,
            }
        )
        return Response(output.data, status=status.HTTP_201_CREATED)


class DashboardSummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        latest_stress = StressInferenceSnapshot.objects.filter(employee=employee).order_by("-window_end").first()
        latest_sample = WearableSample.objects.filter(employee=employee).order_by("-recorded_at").first()

        score = int(round(float(latest_stress.stress_score) * 100)) if latest_stress else 0
        label = latest_stress.risk_level if latest_stress else "sem dados"
        device_name = latest_sample.device_id if latest_sample else "Sem dispositivo"
        last_sync_label = latest_sample.recorded_at.strftime("%d/%m/%Y %H:%M") if latest_sample else "sem sincronizacao"

        output = DashboardSnapshotOutputSerializer(
            {
                "score": max(0, min(100, score)),
                "label": label,
                "deviceName": device_name,
                "lastSyncLabel": last_sync_label,
            }
        )
        return Response(output.data, status=status.HTTP_200_OK)


class BurnoutAssessmentQuestionsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        saved_answers = _latest_assessment_answers(employee)
        questions = [
            question
            for question in BURNOUT_ASSESSMENT_QUESTIONS
            if question["id"] not in ASSESSMENT_PROFILE_FIELD_IDS or question["id"] not in saved_answers
        ]
        output = AssessmentQuestionOutputSerializer(questions, many=True)
        return Response(output.data, status=status.HTTP_200_OK)


class BurnoutAssessmentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        hydrated_payload = _hydrate_assessment_payload(request.data, employee)
        serializer = BurnoutAssessmentInputSerializer(data=hydrated_payload)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        deterministic_score, factors = compute_burnout_composite(payload)
        try:
            prediction = burn_rate_predictor.predict(payload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        composite_score = float(prediction["burn_rate_pred"])
        risk_level = prediction["risk"]

        answers = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "source",
                "notes",
            }
        }
        method_version = prediction.get("model_version") or "burnout-composite-v2-harvard"
        BurnoutAssessment.objects.create(
            employee=employee,
            source=payload["source"],
            answers={
                **answers,
                "model_prediction": prediction,
                "deterministic_score": round(deterministic_score, 4),
                "deterministic_factors": {k: round(v, 4) for k, v in factors.items()},
            },
            composite_score=composite_score,
            risk_level=risk_level,
            method_version=method_version,
            notes=payload.get("notes", ""),
        )

        output = BurnoutAssessmentOutputSerializer(
            {
                "employee_record_id": employee.id,
                "composite_score": round(composite_score, 4),
                "risk_level": risk_level,
                "method_version": method_version,
                "factors": {k: round(v, 4) for k, v in factors.items()},
                "burn_rate_min": prediction.get("burn_rate_min"),
                "burn_rate_max": prediction.get("burn_rate_max"),
                "prediction_source": prediction.get("prediction_source"),
                "fallback_reason": prediction.get("fallback_reason", ""),
                "model_version": prediction.get("model_version"),
                "top_factors": prediction.get("top_factors", []),
                "out_of_distribution": prediction.get("out_of_distribution", False),
                "ood_features": prediction.get("ood_features", []),
                "deterministic_score": round(deterministic_score, 4),
            }
        )
        return Response(output.data, status=status.HTTP_201_CREATED)


def _latest_assessment_answers(employee: EmployeeRecord) -> dict:
    latest_assessment = BurnoutAssessment.objects.filter(employee=employee).order_by("-created_at").first()
    if latest_assessment is None or not isinstance(latest_assessment.answers, dict):
        return {}
    return latest_assessment.answers


def _hydrate_assessment_payload(request_data, employee: EmployeeRecord) -> dict:
    hydrated_payload = dict(request_data)
    saved_answers = _latest_assessment_answers(employee)
    for field in ASSESSMENT_PROFILE_FIELD_IDS:
        if field not in hydrated_payload and field in saved_answers:
            hydrated_payload[field] = saved_answers[field]
    return hydrated_payload


class RiskInferenceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = RiskInferenceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        employee = get_authenticated_employee(request.user)

        burnout_score = payload.get("burnout_composite_score")
        if burnout_score is None:
            latest_assessment = BurnoutAssessment.objects.filter(employee=employee).order_by("-created_at").first()
            burnout_score = float(latest_assessment.composite_score) if latest_assessment else None

        stress_score = payload.get("stress_score")
        if stress_score is None:
            latest_stress = StressInferenceSnapshot.objects.filter(employee=employee).order_by("-window_end").first()
            stress_score = float(latest_stress.stress_score) if latest_stress else None

        try:
            risk_result = compute_final_risk(stress_score, burnout_score)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        recommendation = recommendation_for_risk(risk_result.risk_level)

        RiskTriageDecision.objects.create(
            employee=employee,
            stress_score=risk_result.stress_score,
            burnout_score=risk_result.burnout_score,
            final_score=risk_result.final_score,
            risk_level=risk_result.risk_level,
            recommendation=recommendation,
            inference_mode=risk_result.inference_mode,
            confidence_level=risk_result.confidence_level,
            details={
                "context": payload.get("context", {}),
                "input_availability": {
                    "stress_score": stress_score is not None,
                    "burnout_score": burnout_score is not None,
                },
            },
        )

        output = RiskInferenceOutputSerializer(
            {
                "employee_record_id": employee.id,
                "stress_score": round(risk_result.stress_score, 4),
                "burnout_score": round(risk_result.burnout_score, 4),
                "final_score": round(risk_result.final_score, 4),
                "risk_level": risk_result.risk_level,
                "recommendation": recommendation,
                "model_version": "risk-fusion-v2",
                "inference_mode": risk_result.inference_mode,
                "confidence_level": risk_result.confidence_level,
            }
        )
        return Response(output.data, status=status.HTTP_200_OK)
