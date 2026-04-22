from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from employee.models import EmployeeRecord
from organizations.models import Enterprise
from organizations.serializers import EnterpriseLookupSerializer

from .models import AccountUserGroup, RecoveryPassword, User


class AccountUserGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountUserGroup
        fields = "__all__"


class RecoveryPasswordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecoveryPassword
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "created_at",
            "modified_at",
            "username",
            "password",
            "email",
            "name",
            "desired_name",
            "check_show_again",
            "last_login",
            "last_login_language",
            "is_active",
            "is_staff",
            "is_superuser",
            "is_default",
            "regime",
            "admission_date",
            "birth_date",
            "resignation_date",
            "cpf",
            "github",
            "linkedin",
            "external",
            "groups",
        )
        read_only_fields = (
            "id",
            "created_at",
            "modified_at",
            "last_login",
            "is_superuser",
            "is_staff",
            "is_active",
        )

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        username = validated_data.pop("username")
        return User.objects.create_user(username=username, password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    name = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=256)
    desired_name = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=256)
    enterprise_id = serializers.IntegerField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username ja esta em uso.")
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email ja esta em uso.")
        return value

    def validate_enterprise_id(self, value):
        if not Enterprise.objects.filter(id=value, active=True).exists():
            raise serializers.ValidationError("Empresa selecionada nao encontrada ou inativa.")
        return value

    def create(self, validated_data):
        enterprise_id = validated_data.pop("enterprise_id")
        enterprise = Enterprise.objects.get(id=enterprise_id, active=True)
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)
            EmployeeRecord.objects.create(user=user, enterprise=enterprise)
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = (attrs.get("username") or "").strip()
        email = (attrs.get("email") or "").strip()
        password = attrs["password"]

        if not username and not email:
            raise serializers.ValidationError({"detail": "Informe username ou email."})

        user = None
        if username:
            user = authenticate(username=username, password=password)
        if user is None and email:
            candidate = User.objects.filter(email__iexact=email).first()
            if candidate and candidate.check_password(password) and candidate.is_active:
                user = candidate

        if user is None:
            raise serializers.ValidationError({"detail": "Credenciais invalidas."})
        employee = getattr(user, "employee_record", None)
        if employee is None or employee.enterprise_id is None:
            raise serializers.ValidationError({"detail": "Usuario nao vinculado a employee e empresa."})
        attrs["user"] = user
        return attrs


class UserAuthOutputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    access = serializers.CharField()
    refresh = serializers.CharField()
    has_employee_profile = serializers.BooleanField()
    employee_record_id = serializers.IntegerField(allow_null=True)
    enterprise = EnterpriseLookupSerializer(allow_null=True)

    @staticmethod
    def from_user(user):
        refresh = RefreshToken.for_user(user)
        employee = getattr(user, "employee_record", None)
        enterprise = employee.enterprise if employee and employee.enterprise_id else None
        return {
            "user_id": user.id,
            "username": user.username,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "has_employee_profile": employee is not None,
            "employee_record_id": employee.id if employee else None,
            "enterprise": EnterpriseLookupSerializer(enterprise).data if enterprise else None,
        }
