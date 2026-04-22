from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from employee.models import EmployeeProfile, EmployeeRecord
from .models import Enterprise, EnterpriseCommercialProfile, TherapyGroup, TherapyGroupMember

User = get_user_model()


def unique_username(seed: str) -> str:
    base = slugify(seed or "usuario").replace("-", ".")[:56] or "usuario"
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base}.{suffix}"[:64]
    return candidate


class EnterpriseLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enterprise
        fields = ("id", "name", "code", "kind")


def enterprise_payload(enterprise: Enterprise | None) -> dict | None:
    if enterprise is None:
        return None

    profile = getattr(enterprise, "commercial_profile", None)
    return {
        "id": enterprise.id,
        "name": enterprise.name,
        "code": enterprise.code,
        "kind": enterprise.kind,
        "taxId": profile.tax_id if profile else "",
        "contactName": profile.contact_name if profile else "",
        "contactEmail": profile.contact_email if profile else "",
        "companySize": profile.company_size if profile else "",
        "planId": profile.plan_id if profile else "",
    }


def auth_payload(user) -> dict:
    refresh = RefreshToken.for_user(user)
    employee = getattr(user, "employee_record", None)
    enterprise = employee.enterprise if employee and employee.enterprise_id else None
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email or "",
        "name": user.name or user.desired_name or user.username,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "employee_record_id": employee.id if employee else None,
        "enterprise": enterprise_payload(enterprise),
    }


class EnterpriseSignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=256)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email ja esta em uso.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=unique_username(validated_data["email"].split("@")[0]),
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
        )


class EnterpriseCompanySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    taxId = serializers.CharField(max_length=32, required=False, allow_blank=True)
    contactName = serializers.CharField(max_length=160, required=False, allow_blank=True)
    contactEmail = serializers.EmailField(required=False, allow_blank=True)
    companySize = serializers.CharField(max_length=40, required=False, allow_blank=True)
    planId = serializers.CharField(max_length=40, required=False, allow_blank=True)


class EnterpriseUserCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=256)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    regime = serializers.CharField(max_length=1, required=False, allow_blank=True)
    active = serializers.BooleanField(required=False, default=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email ja esta em uso.")
        return value

    def create_for_enterprise(self, enterprise: Enterprise):
        payload = self.validated_data
        password = payload.get("password") or User.objects.make_random_password(length=12)
        with transaction.atomic():
            user = User.objects.create_user(
                username=unique_username(payload["email"].split("@")[0]),
                email=payload["email"],
                password=password,
                name=payload["name"],
                regime=payload.get("regime") or User.Regime.HOME_OFFICE,
                is_active=payload.get("active", True),
            )
            employee = EmployeeRecord.objects.create(user=user, enterprise=enterprise, active=payload.get("active", True))
            EmployeeProfile.objects.create(
                employee=employee,
                job_title=payload.get("job_title", ""),
                department=payload.get("department", ""),
            )
        return user


class TherapyGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    focus = serializers.CharField(max_length=180)
    facilitator_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    next_session_at = serializers.DateTimeField(required=False, allow_null=True)
    member_user_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True, required=False)

    def create_for_enterprise(self, enterprise: Enterprise):
        member_user_ids = self.validated_data.pop("member_user_ids", [])
        users = list(
            User.objects.filter(
                id__in=member_user_ids,
                employee_record__enterprise=enterprise,
                employee_record__active=True,
            )
        )
        found_ids = {user.id for user in users}
        invalid_ids = set(member_user_ids) - found_ids
        if invalid_ids:
            raise serializers.ValidationError({"member_user_ids": "Usuarios fora da empresa nao podem entrar no grupo."})

        with transaction.atomic():
            group = TherapyGroup.objects.create(enterprise=enterprise, **self.validated_data)
            TherapyGroupMember.objects.bulk_create([TherapyGroupMember(group=group, user=user) for user in users])
        return group
