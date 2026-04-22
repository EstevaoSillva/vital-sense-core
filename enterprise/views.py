from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from employee.models import BurnoutAssessment, EmployeeProfile, EmployeeRecord, Recommendation, RiskTriageDecision, StressInferenceSnapshot, WearableSample

from .models import Enterprise, EnterpriseCommercialProfile, TherapyGroup
from .serializers import (
    EnterpriseCompanySerializer,
    EnterpriseSignupSerializer,
    EnterpriseUserCreateSerializer,
    TherapyGroupCreateSerializer,
    auth_payload,
    enterprise_payload,
)

User = get_user_model()


def authenticated_employee(user) -> EmployeeRecord:
    employee = getattr(user, "employee_record", None)
    if employee is None:
        raise PermissionDenied("Usuario autenticado ainda nao esta vinculado a uma empresa.")
    return employee


def authenticated_enterprise(user) -> Enterprise:
    employee = authenticated_employee(user)
    if employee.enterprise_id is None:
        raise PermissionDenied("Usuario autenticado nao possui empresa.")
    return employee.enterprise


def unique_enterprise_code(name: str) -> str:
    base = slugify(name or "empresa").upper().replace("-", "")[:90] or "EMPRESA"
    candidate = base
    suffix = 1
    while Enterprise.objects.filter(code=candidate).exists():
        suffix += 1
        candidate = f"{base}{suffix}"[:100]
    return candidate


def score_percent(score) -> int:
    if score is None:
        return 0
    value = float(score)
    if value <= 1:
        value *= 100
    return max(0, min(100, int(round(value))))


def risk_from_scores(stress: int, burnout: int, explicit: str = "") -> str:
    risk = (explicit or "").lower()
    if risk == "high":
        return "Alto"
    if risk == "moderate":
        return "Médio"
    if risk == "low":
        return "Baixo"
    value = max(stress, burnout)
    if value >= 70:
        return "Alto"
    if value >= 45:
        return "Médio"
    return "Baixo"


def risk_slug(label: str) -> str:
    return {"Alto": "alto", "Médio": "medio", "Baixo": "baixo"}.get(label, "baixo")


def label_datetime(value) -> str:
    if value is None:
        return "Sem coleta"
    local_value = timezone.localtime(value)
    if local_value.date() == timezone.localdate():
        return f"Hoje, {local_value:%H:%M}"
    return local_value.strftime("%d/%m/%Y %H:%M")


def trend_from_stress(employee: EmployeeRecord) -> str:
    snapshots = list(employee.stress_snapshots.filter(active=True).order_by("-window_end")[:2])
    if len(snapshots) < 2:
        return "stable"
    delta = score_percent(snapshots[0].stress_score) - score_percent(snapshots[1].stress_score)
    if delta >= 3:
        return "up"
    if delta <= -3:
        return "down"
    return "stable"


def profile_for(employee: EmployeeRecord):
    return getattr(employee, "mobile_profile", None)


def employee_payload(employee: EmployeeRecord) -> dict:
    user = employee.user
    profile = profile_for(employee)
    latest_stress = employee.stress_snapshots.filter(active=True).order_by("-window_end").first()
    latest_burnout = employee.burnout_assessments.filter(active=True).order_by("-created_at").first()
    latest_triage = employee.risk_triage_decisions.filter(active=True).order_by("-created_at").first()
    latest_sample = employee.wearable_samples.filter(active=True).order_by("-recorded_at").first()

    stress = score_percent(latest_stress.stress_score if latest_stress else None)
    burnout = score_percent(latest_burnout.composite_score if latest_burnout else None)
    risk = risk_from_scores(stress, burnout, latest_triage.risk_level if latest_triage else "")
    name = user.name or user.desired_name or user.username
    parts = [part for part in name.split(" ") if part]
    avatar = "".join(part[0] for part in parts[:2]).upper() or "U"
    sleep_hours = 0
    if latest_burnout and isinstance(latest_burnout.answers, dict):
        sleep_hours = latest_burnout.answers.get("sleep_hours") or 0

    return {
        "id": str(user.id),
        "userId": user.id,
        "employeeRecordId": employee.id,
        "name": name,
        "email": user.email or "",
        "role": profile.job_title if profile else "",
        "department": profile.department if profile and profile.department else "Sem departamento",
        "avatar": avatar,
        "stress": stress,
        "burnout": burnout,
        "sleepHours": float(sleep_hours or 0),
        "hrv": 0,
        "trend": trend_from_stress(employee),
        "risk": risk,
        "vitalScore": max(0, min(100, 100 - int(round((stress + burnout) / 2)))),
        "active": employee.active and user.is_active,
        "lastSyncLabel": label_datetime(latest_sample.recorded_at if latest_sample else latest_stress.window_end if latest_stress else None),
        "adherenceScore": 100 if latest_sample or latest_stress else 0,
    }


def enterprise_employees(enterprise: Enterprise):
    return (
        EmployeeRecord.objects.filter(enterprise=enterprise, active=True, user__is_active=True)
        .select_related("user", "mobile_profile", "enterprise")
        .prefetch_related("stress_snapshots", "burnout_assessments", "risk_triage_decisions", "wearable_samples")
        .order_by("user__name", "user__email")
    )


class EnterpriseSignupAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = EnterpriseSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(auth_payload(user), status=status.HTTP_201_CREATED)


class EnterpriseCompanyAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(enterprise_payload(authenticated_enterprise(request.user)), status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        return self.upsert(request)

    def patch(self, request, *args, **kwargs):
        return self.upsert(request)

    def upsert(self, request):
        serializer = EnterpriseCompanySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        employee = getattr(request.user, "employee_record", None)
        enterprise = employee.enterprise if employee and employee.enterprise_id else None

        if enterprise is None:
            enterprise = Enterprise.objects.create(
                name=payload["name"],
                code=payload.get("code") or unique_enterprise_code(payload["name"]),
                kind="company",
            )
            employee, _ = EmployeeRecord.objects.get_or_create(user=request.user, defaults={"enterprise": enterprise})
            if employee.enterprise_id is None:
                employee.enterprise = enterprise
                employee.save(update_fields=["enterprise", "modified_at"])
        else:
            enterprise.name = payload["name"]
            if payload.get("code"):
                enterprise.code = payload["code"]
            enterprise.save(update_fields=["name", "code", "modified_at"])

        profile, _ = EnterpriseCommercialProfile.objects.get_or_create(enterprise=enterprise)
        profile.tax_id = payload.get("taxId", "")
        profile.contact_name = payload.get("contactName", "")
        profile.contact_email = payload.get("contactEmail", "")
        profile.company_size = payload.get("companySize", "")
        profile.plan_id = payload.get("planId", "")
        profile.save()
        return Response(enterprise_payload(enterprise), status=status.HTTP_200_OK)


class EnterpriseDashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        enterprise = authenticated_enterprise(request.user)
        employees = [employee_payload(employee) for employee in enterprise_employees(enterprise)]
        total = len(employees)
        high_count = len([item for item in employees if item["risk"] == "Alto"])
        avg_stress = round(sum(item["stress"] for item in employees) / total) if total else 0
        org_score = round(sum(item["vitalScore"] for item in employees) / total) if total else 0
        avg_burnout = round(sum(item["burnout"] for item in employees) / total) if total else 0
        predicted_loss = high_count * 8400 + len([item for item in employees if item["risk"] == "Médio"]) * 2100

        department_map = defaultdict(lambda: {"department": "", "alto": 0, "medio": 0, "baixo": 0})
        for item in employees:
            bucket = department_map[item["department"]]
            bucket["department"] = item["department"]
            bucket[risk_slug(item["risk"])] += 1

        stress_trend = [
            {"week": f"Sem {index + 1}", "stress": avg_stress, "sleep": 0, "productivity": max(0, 100 - avg_stress)}
            for index in range(8)
        ]

        alerts = []
        for department in sorted(department_map.values(), key=lambda value: value["alto"], reverse=True)[:4]:
            if department["alto"]:
                alerts.append(
                    {
                        "id": len(alerts) + 1,
                        "dept": department["department"],
                        "message": f"{department['alto']} colaborador(es) com risco alto em {department['department']}.",
                        "severity": "alta",
                        "eta": "Imediato",
                    }
                )

        return Response(
            {
                "kpis": {
                    "orgScore": org_score,
                    "highRiskPct": round((high_count / total) * 100) if total else 0,
                    "avgStress": avg_stress,
                    "burnoutTrend": avg_burnout,
                    "predictedLoss": predicted_loss,
                    "totalEmployees": total,
                },
                "stressTrend": stress_trend,
                "departmentRisk": list(department_map.values()),
                "aiAlerts": alerts,
                "benchmark": {"company": org_score, "industry": 64, "topQuartile": 81},
            },
            status=status.HTTP_200_OK,
        )


class EnterpriseUserListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        enterprise = authenticated_enterprise(request.user)
        rows = [employee_payload(employee) for employee in enterprise_employees(enterprise)]
        search = (request.query_params.get("search") or "").strip().lower()
        department = (request.query_params.get("department") or "").strip()
        risk = (request.query_params.get("risk") or "").strip()

        if search:
            rows = [
                row
                for row in rows
                if search in row["name"].lower() or search in row["email"].lower() or search in row["role"].lower()
            ]
        if department and department != "Todos":
            rows = [row for row in rows if row["department"] == department]
        if risk and risk != "Todos":
            rows = [row for row in rows if row["risk"] == risk]
        return Response(rows, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        enterprise = authenticated_enterprise(request.user)
        serializer = EnterpriseUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.create_for_enterprise(enterprise)
        return Response(employee_payload(user.employee_record), status=status.HTTP_201_CREATED)


class EnterpriseRecommendationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        enterprise = authenticated_enterprise(request.user)
        recommendations = (
            Recommendation.objects.filter(
                Q(employee__enterprise=enterprise) | Q(employee__isnull=True),
                active=True,
            )
            .select_related("employee__user", "employee__mobile_profile")
            .order_by("-created_at", "-id")[:50]
        )
        payload = []
        for recommendation in recommendations:
            employee = recommendation.employee
            profile = profile_for(employee) if employee else None
            payload.append(
                {
                    "id": recommendation.id,
                    "employee": employee.user.name if employee else "Equipe",
                    "dept": profile.department if profile and profile.department else "Geral",
                    "action": recommendation.title,
                    "priority": "Média" if recommendation.priority == "Media" else recommendation.priority,
                    "reason": recommendation.reason or recommendation.description,
                }
            )
        return Response(payload, status=status.HTTP_200_OK)


class TherapyGroupListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        enterprise = authenticated_enterprise(request.user)
        groups = TherapyGroup.objects.filter(enterprise=enterprise, active=True).prefetch_related("memberships").order_by("-created_at", "-id")
        return Response([self.payload(group) for group in groups], status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        enterprise = authenticated_enterprise(request.user)
        serializer = TherapyGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.create_for_enterprise(enterprise)
        return Response(self.payload(group), status=status.HTTP_201_CREATED)

    def payload(self, group: TherapyGroup) -> dict:
        return {
            "id": group.id,
            "name": group.name,
            "members": group.memberships.filter(active=True).count(),
            "focus": group.focus,
            "facilitator": group.facilitator_name or "A definir",
            "nextSession": label_datetime(group.next_session_at),
            "trend": "estável",
            "status": group.status,
        }
