from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmployeeRecord

User = get_user_model()


class EmployeeLoginSerializer(serializers.Serializer):
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

        if not hasattr(user, "employee_record"):
            raise serializers.ValidationError({"detail": "Usuario nao vinculado a employee."})

        attrs["user"] = user
        return attrs


class EmployeeAuthOutputSerializer(serializers.Serializer):
    employee_record_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    access = serializers.CharField()
    refresh = serializers.CharField()

    @staticmethod
    def from_user(user):
        refresh = RefreshToken.for_user(user)
        return {
            "employee_record_id": user.employee_record_id,
            "user_id": user.id,
            "username": user.username,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class EmployeeRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeRecord
        fields = "__all__"


class BurnRatePredictionInputSerializer(serializers.Serializer):
    GENDER_CHOICES = [("female", "Female"), ("male", "Male"), ("other", "Other")]
    COMPANY_TYPE_CHOICES = [("service", "Service"), ("product", "Product")]
    DESIGNATION_CHOICES = [(0, "Trainee"), (1, "Junior"), (2, "Full"), (3, "Senior"), (4, "Master"), (5, "Executive")]
    SCALE_1_TO_10_CHOICES = [(i, str(i)) for i in range(1, 11)]
    SCALE_1_TO_5_CHOICES = [(i, str(i)) for i in range(1, 6)]

    gender = serializers.ChoiceField(
        choices=GENDER_CHOICES,
        help_text="Genero do colaborador.",
    )
    company_type = serializers.ChoiceField(
        choices=COMPANY_TYPE_CHOICES,
        help_text="Tipo da empresa.",
    )
    wfh_setup_available = serializers.BooleanField(help_text="Se possui setup de home office.")
    designation = serializers.ChoiceField(
        choices=DESIGNATION_CHOICES,
        help_text="Nivel de senioridade.",
    )
    resource_allocation = serializers.ChoiceField(
        choices=SCALE_1_TO_10_CHOICES,
        help_text="Carga de trabalho (1 a 10).",
    )
    work_hours_per_week = serializers.IntegerField(
        min_value=1,
        max_value=120,
        help_text="Horas de trabalho por semana.",
        style={"placeholder": "Ex.: 44"},
    )
    sleep_hours = serializers.FloatField(
        min_value=0.0,
        max_value=24.0,
        help_text="Horas medias de sono por dia.",
        style={"placeholder": "Ex.: 7.0"},
    )
    work_life_balance_score = serializers.ChoiceField(
        choices=SCALE_1_TO_5_CHOICES,
        help_text="Equilibrio vida-trabalho (1 a 5).",
    )
    manager_support_score = serializers.ChoiceField(
        choices=SCALE_1_TO_5_CHOICES,
        help_text="Suporte da lideranca (1 a 5).",
    )
    deadline_pressure_score = serializers.ChoiceField(
        choices=SCALE_1_TO_5_CHOICES,
        help_text="Pressao de prazos (1 a 5).",
    )
    team_size = serializers.IntegerField(
        min_value=1,
        max_value=1000,
        help_text="Quantidade de pessoas no time.",
        style={"placeholder": "Ex.: 8"},
    )
    recognition_frequency = serializers.IntegerField(
        min_value=0,
        max_value=1000,
        help_text="Frequencia de reconhecimento.",
        style={"placeholder": "Ex.: 2"},
    )
    exhaustion_score = serializers.ChoiceField(
        choices=SCALE_1_TO_5_CHOICES,
        help_text="Exaustao emocional (1 a 5).",
    )
    cynicism_score = serializers.ChoiceField(
        choices=SCALE_1_TO_5_CHOICES,
        help_text="Cinismo/distanciamento do trabalho (1 a 5).",
    )
    efficacy_score = serializers.ChoiceField(
        choices=SCALE_1_TO_5_CHOICES,
        help_text="Eficacia profissional percebida (1 a 5).",
    )


class BurnRatePredictionOutputSerializer(serializers.Serializer):
    burn_rate_pred = serializers.FloatField()
    burn_rate_min = serializers.FloatField()
    burn_rate_max = serializers.FloatField()
    risk = serializers.CharField()
    model_version = serializers.CharField()
    prediction_source = serializers.CharField(required=False)
    fallback_reason = serializers.CharField(required=False, allow_blank=True)
    out_of_distribution = serializers.BooleanField(required=False)
    ood_features = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    top_factors = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )


class WearableSampleInputSerializer(serializers.Serializer):
    sensor_type = serializers.ChoiceField(choices=["hr", "eda", "temp", "acc", "bvp", "hrv"])
    recorded_at = serializers.DateTimeField()
    value = serializers.FloatField()
    unit = serializers.CharField(required=False, allow_blank=True, default="")
    quality = serializers.FloatField(min_value=0.0, max_value=1.0, required=False, default=1.0)
    payload = serializers.DictField(required=False, default=dict)


class WearableIngestionSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=80)
    samples = WearableSampleInputSerializer(many=True, allow_empty=False)


class WearableIngestionOutputSerializer(serializers.Serializer):
    employee_record_id = serializers.IntegerField()
    ingested_samples = serializers.IntegerField()
    stress_score = serializers.FloatField()
    stress_risk = serializers.CharField()
    trigger_recommended = serializers.BooleanField()
    window_start = serializers.DateTimeField()
    window_end = serializers.DateTimeField()
    signal_quality = serializers.FloatField()
    model_version = serializers.CharField()


class DashboardSnapshotOutputSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0, max_value=100)
    label = serializers.CharField()
    deviceName = serializers.CharField()
    lastSyncLabel = serializers.CharField()


class BurnoutAssessmentInputSerializer(serializers.Serializer):
    GENDER_CHOICES = BurnRatePredictionInputSerializer.GENDER_CHOICES
    COMPANY_TYPE_CHOICES = BurnRatePredictionInputSerializer.COMPANY_TYPE_CHOICES
    DESIGNATION_CHOICES = BurnRatePredictionInputSerializer.DESIGNATION_CHOICES

    source = serializers.ChoiceField(choices=["manual", "triggered", "scheduled"], default="manual")
    gender = serializers.ChoiceField(choices=GENDER_CHOICES)
    company_type = serializers.ChoiceField(choices=COMPANY_TYPE_CHOICES)
    wfh_setup_available = serializers.BooleanField()
    designation = serializers.ChoiceField(choices=DESIGNATION_CHOICES)
    resource_allocation = serializers.IntegerField(min_value=1, max_value=10)
    work_hours_per_week = serializers.IntegerField(min_value=1, max_value=120)
    sleep_hours = serializers.FloatField(min_value=0.0, max_value=24.0)
    team_size = serializers.IntegerField(min_value=1, max_value=1000)
    recognition_frequency = serializers.IntegerField(min_value=0, max_value=1000)
    exhaustion_score = serializers.IntegerField(min_value=1, max_value=5)
    cynicism_score = serializers.IntegerField(min_value=1, max_value=5)
    efficacy_score = serializers.IntegerField(min_value=1, max_value=5)
    work_life_balance_score = serializers.IntegerField(min_value=1, max_value=5)
    manager_support_score = serializers.IntegerField(min_value=1, max_value=5)
    deadline_pressure_score = serializers.IntegerField(min_value=1, max_value=5)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class AssessmentQuestionOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class AssessmentQuestionOutputSerializer(serializers.Serializer):
    id = serializers.CharField()
    category = serializers.CharField()
    text = serializers.CharField()
    input_type = serializers.CharField()
    scale_labels = serializers.ListField(child=serializers.CharField(), required=False)
    options = AssessmentQuestionOptionSerializer(many=True, required=False)
    min_value = serializers.FloatField(required=False, allow_null=True)
    max_value = serializers.FloatField(required=False, allow_null=True)
    required = serializers.BooleanField(default=True)
    help_text = serializers.CharField(required=False, allow_blank=True)


class BurnoutAssessmentOutputSerializer(serializers.Serializer):
    employee_record_id = serializers.IntegerField()
    composite_score = serializers.FloatField()
    risk_level = serializers.CharField()
    method_version = serializers.CharField()
    factors = serializers.DictField()
    burn_rate_min = serializers.FloatField(required=False)
    burn_rate_max = serializers.FloatField(required=False)
    prediction_source = serializers.CharField(required=False)
    fallback_reason = serializers.CharField(required=False, allow_blank=True)
    model_version = serializers.CharField(required=False)
    top_factors = serializers.ListField(child=serializers.DictField(), required=False)
    out_of_distribution = serializers.BooleanField(required=False)
    ood_features = serializers.ListField(child=serializers.CharField(), required=False)
    deterministic_score = serializers.FloatField(required=False)


class RiskInferenceInputSerializer(serializers.Serializer):
    burnout_composite_score = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    stress_score = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    context = serializers.DictField(required=False, default=dict)


class RiskInferenceOutputSerializer(serializers.Serializer):
    employee_record_id = serializers.IntegerField()
    stress_score = serializers.FloatField()
    burnout_score = serializers.FloatField()
    final_score = serializers.FloatField()
    risk_level = serializers.CharField()
    recommendation = serializers.CharField()
    model_version = serializers.CharField()
    inference_mode = serializers.CharField(required=False)
    confidence_level = serializers.CharField(required=False)
