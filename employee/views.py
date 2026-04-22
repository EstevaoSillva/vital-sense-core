from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from ml.burnout.predictor import BurnRatePredictor
from .filters import EmployeeRecordFilter
from .models import (
    Article,
    BurnoutAssessment,
    EmployeeRecord,
    EmployeeProfile,
    MobileNotification,
    Recommendation,
    RiskTriageDecision,
    StressInferenceSnapshot,
    WearableSample,
    WatchDeviceStatus,
)
from .serializers import (
    AssessmentQuestionOutputSerializer,
    ArticleDetailOutputSerializer,
    ArticleSummaryOutputSerializer,
    BurnoutAssessmentInputSerializer,
    BurnoutAssessmentOutputSerializer,
    CollectionDetailOutputSerializer,
    CollectionSessionOutputSerializer,
    DashboardSnapshotOutputSerializer,
    EmployeeAuthOutputSerializer,
    EmployeeLoginSerializer,
    BurnRatePredictionInputSerializer,
    BurnRatePredictionOutputSerializer,
    EmployeeRecordSerializer,
    InsightSummaryOutputSerializer,
    NotificationItemOutputSerializer,
    RecommendationOutputSerializer,
    RiskInferenceInputSerializer,
    RiskInferenceOutputSerializer,
    UserProfileOutputSerializer,
    WearableIngestionOutputSerializer,
    WearableIngestionSerializer,
    WatchSyncStatusOutputSerializer,
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


def _score_percent(score) -> int:
    return max(0, min(100, int(round(float(score) * 100))))


def _label_datetime(value) -> str:
    if value is None:
        return "sem sincronizacao"
    local_value = timezone.localtime(value)
    if local_value.date() == timezone.localdate():
        return f"Hoje, {local_value:%H:%M}"
    return local_value.strftime("%d/%m/%Y %H:%M")


def _notification_datetime(value) -> str:
    local_value = timezone.localtime(value)
    if local_value.date() == timezone.localdate():
        return f"{local_value:%H:%M} - Hoje"
    return local_value.strftime("%d/%m/%Y %H:%M")


def _duration_label(start, end) -> str:
    total_minutes = max(1, int(round((end - start).total_seconds() / 60)))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}min"
    if hours:
        return f"{hours}h"
    return f"{minutes} min"


def _quality_label(signal_quality: float) -> str:
    if signal_quality >= 0.85:
        return "Excelente"
    if signal_quality >= 0.65:
        return "Boa"
    if signal_quality >= 0.40:
        return "Regular"
    return "Baixa"


def _device_name_for_snapshot(snapshot: StressInferenceSnapshot) -> str:
    sample = (
        WearableSample.objects.filter(
            employee=snapshot.employee,
            recorded_at__gte=snapshot.window_start,
            recorded_at__lte=snapshot.window_end,
        )
        .order_by("-recorded_at")
        .first()
    )
    if sample:
        return sample.device_id
    latest_status = WatchDeviceStatus.objects.filter(employee=snapshot.employee, active=True).first()
    return latest_status.device_name if latest_status else "Sem dispositivo"


def _collection_session_payload(snapshot: StressInferenceSnapshot) -> dict:
    return {
        "id": str(snapshot.id),
        "title": f"Sessao de stress #{snapshot.id}",
        "timestamp": _label_datetime(snapshot.window_end),
        "durationLabel": _duration_label(snapshot.window_start, snapshot.window_end),
        "score": _score_percent(snapshot.stress_score),
        "label": snapshot.risk_level,
        "quality": _quality_label(float(snapshot.signal_quality)),
        "deviceName": _device_name_for_snapshot(snapshot),
    }


def _trend_label(values: list[int]) -> str:
    if len(values) < 2:
        return "Estavel"
    delta = values[-1] - values[0]
    if delta <= -5:
        return "Melhorando"
    if delta >= 5:
        return "Atencao"
    return "Estavel"


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
        WatchDeviceStatus.objects.update_or_create(
            employee=employee,
            device_name=payload["device_id"],
            defaults={
                "is_connected": True,
                "battery_percent": int(samples[-1].payload.get("battery_percent", 0)) if samples else 0,
                "last_sync_at": stress_result.window_end,
                "syncing": False,
                "active": True,
            },
        )
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


class UserProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        profile = EmployeeProfile.objects.filter(employee=employee, active=True).first()
        user = request.user
        output = UserProfileOutputSerializer(
            {
                "name": user.name or user.desired_name or user.username,
                "email": user.email or "",
                "jobTitle": profile.job_title if profile else "",
                "company": employee.enterprise.name if employee.enterprise_id else "",
                "workSchedule": profile.work_schedule if profile else "",
            }
        )
        return Response(output.data, status=status.HTTP_200_OK)


class WatchSyncStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        device_status = WatchDeviceStatus.objects.filter(employee=employee, active=True).first()
        latest_sample = WearableSample.objects.filter(employee=employee).order_by("-recorded_at").first()
        if device_status:
            payload = {
                "deviceName": device_status.device_name,
                "isConnected": device_status.is_connected,
                "batteryPercent": max(0, min(100, int(device_status.battery_percent))),
                "lastSyncLabel": _label_datetime(device_status.last_sync_at),
                "syncing": device_status.syncing,
            }
        else:
            payload = {
                "deviceName": latest_sample.device_id if latest_sample else "Sem dispositivo",
                "isConnected": latest_sample is not None,
                "batteryPercent": 0,
                "lastSyncLabel": _label_datetime(latest_sample.recorded_at if latest_sample else None),
                "syncing": False,
            }
        output = WatchSyncStatusOutputSerializer(payload)
        return Response(output.data, status=status.HTTP_200_OK)


class CollectionListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        snapshots = StressInferenceSnapshot.objects.filter(employee=employee, active=True).order_by("-window_end", "-id")[:30]
        output = CollectionSessionOutputSerializer([_collection_session_payload(snapshot) for snapshot in snapshots], many=True)
        return Response(output.data, status=status.HTTP_200_OK)


class CollectionDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, collection_id, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        snapshot = StressInferenceSnapshot.objects.filter(employee=employee, id=collection_id, active=True).first()
        if snapshot is None:
            return Response({"detail": "Coleta nao encontrada."}, status=status.HTTP_404_NOT_FOUND)

        window_samples = WearableSample.objects.filter(
            employee=employee,
            recorded_at__gte=snapshot.window_start,
            recorded_at__lte=snapshot.window_end,
        ).order_by("recorded_at")
        heart_rate_points = [
            int(round(sample.value))
            for sample in window_samples.filter(sensor_type=WearableSample.SensorType.HR).order_by("recorded_at")[:60]
        ]
        stress_points = [
            _score_percent(item.stress_score)
            for item in StressInferenceSnapshot.objects.filter(employee=employee, window_end__lte=snapshot.window_end)
            .order_by("-window_end")[:10]
        ]
        stress_points.reverse()
        sensors = list(
            WearableSample.objects.filter(
                employee=employee,
                recorded_at__gte=snapshot.window_start,
                recorded_at__lte=snapshot.window_end,
            )
            .order_by("sensor_type")
            .values_list("sensor_type", flat=True)
            .distinct()
        )
        payload = {
            "session": _collection_session_payload(snapshot),
            "heartRatePoints": heart_rate_points,
            "stressPoints": stress_points,
            "sensors": sensors,
            "observation": f"Risco {snapshot.risk_level} com qualidade de sinal {_quality_label(float(snapshot.signal_quality)).lower()}.",
            "recommendation": recommendation_for_risk(snapshot.risk_level),
        }
        output = CollectionDetailOutputSerializer(payload)
        return Response(output.data, status=status.HTTP_200_OK)


class InsightSummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        stress_values = [
            _score_percent(snapshot.stress_score)
            for snapshot in StressInferenceSnapshot.objects.filter(employee=employee, active=True).order_by("-window_end")[:10]
        ]
        stress_values.reverse()
        burnout_values = [
            _score_percent(assessment.composite_score)
            for assessment in BurnoutAssessment.objects.filter(employee=employee, active=True).order_by("-created_at")[:6]
        ]
        burnout_values.reverse()
        latest_assessment = BurnoutAssessment.objects.filter(employee=employee, active=True).order_by("-created_at").first()
        critical_factors = []
        if latest_assessment and isinstance(latest_assessment.answers, dict):
            factors = latest_assessment.answers.get("deterministic_factors", {})
            if isinstance(factors, dict):
                critical_factors = [key for key, value in sorted(factors.items(), key=lambda item: item[1], reverse=True)[:3]]

        output = InsightSummaryOutputSerializer(
            {
                "weeklyStress": stress_values[-7:],
                "monthlyStress": stress_values,
                "burnoutRiskTrend": burnout_values,
                "criticalFactors": critical_factors,
                "trendLabel": _trend_label(stress_values or burnout_values),
            }
        )
        return Response(output.data, status=status.HTTP_200_OK)


class RecommendationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        recommendations = Recommendation.objects.filter(
            Q(employee=employee) | Q(employee__isnull=True),
            active=True,
        ).order_by("-created_at", "-id")[:30]
        payload = [
            {
                "id": str(recommendation.id),
                "title": recommendation.title,
                "description": recommendation.description,
                "reason": recommendation.reason,
                "priority": recommendation.priority,
            }
            for recommendation in recommendations
        ]
        output = RecommendationOutputSerializer(payload, many=True)
        return Response(output.data, status=status.HTTP_200_OK)


class ArticleListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        articles = Article.objects.filter(active=True).order_by("-created_at", "-id")[:50]
        payload = [
            {
                "id": str(article.id),
                "title": article.title,
                "category": article.category,
                "readTimeMinutes": article.read_time_minutes,
            }
            for article in articles
        ]
        output = ArticleSummaryOutputSerializer(payload, many=True)
        return Response(output.data, status=status.HTTP_200_OK)


class ArticleDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, article_id, *args, **kwargs):
        article = Article.objects.filter(id=article_id, active=True).prefetch_related("sections").first()
        if article is None:
            return Response({"detail": "Artigo nao encontrado."}, status=status.HTTP_404_NOT_FOUND)
        payload = {
            "id": str(article.id),
            "title": article.title,
            "category": article.category,
            "summary": article.summary,
            "author": article.author,
            "sections": [
                {
                    "heading": section.heading,
                    "body": section.body,
                }
                for section in article.sections.filter(active=True).order_by("order", "id")
            ],
            "watchSummary": article.watch_summary,
        }
        output = ArticleDetailOutputSerializer(payload)
        return Response(output.data, status=status.HTTP_200_OK)


class NotificationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        employee = get_authenticated_employee(request.user)
        notifications = MobileNotification.objects.filter(employee=employee, active=True).order_by("-occurred_at", "-id")[:50]
        payload = [
            {
                "id": str(notification.id),
                "category": notification.category,
                "title": notification.title,
                "description": notification.description,
                "timestamp": _notification_datetime(notification.occurred_at),
            }
            for notification in notifications
        ]
        output = NotificationItemOutputSerializer(payload, many=True)
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
