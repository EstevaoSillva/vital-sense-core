from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from core.models import ModelBase


class EmployeeRecord(ModelBase):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        db_column="id_user",
        related_name="employee_record",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        verbose_name=("User"),
        help_text="Usuario autenticado associado ao colaborador.",
    )
    enterprise = models.ForeignKey(
        "organizations.Enterprise",
        db_column="id_enterprise",
        related_name="employees",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=("Enterprise"),
        help_text="Empresa cadastrada associada ao colaborador.",
    )

    history = HistoricalRecords(table_name='"history"."employee_record_history"')

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["user", "active"]),
            models.Index(fields=["enterprise", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.id}:{self.user_id}"


class EmployeeProfile(ModelBase):
    employee = models.OneToOneField(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="mobile_profile",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    job_title = models.CharField(
        db_column="tx_job_title",
        max_length=120,
        blank=True,
        default="",
        verbose_name=("Job title"),
    )
    department = models.CharField(
        db_column="tx_department",
        max_length=120,
        blank=True,
        default="",
        verbose_name=("Department"),
    )
    work_schedule = models.CharField(
        db_column="tx_work_schedule",
        max_length=120,
        blank=True,
        default="",
        verbose_name=("Work schedule"),
    )

    history = HistoricalRecords(table_name='"history"."employee_profile_history"')

    class Meta:
        ordering = ["employee_id"]
        indexes = [models.Index(fields=["employee", "active"])]

    def __str__(self) -> str:
        return f"{self.employee_id}:{self.job_title}"


class WatchDeviceStatus(ModelBase):
    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="watch_device_statuses",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    device_name = models.CharField(
        db_column="tx_device_name",
        max_length=120,
        verbose_name=("Device name"),
    )
    is_connected = models.BooleanField(
        db_column="cs_is_connected",
        default=False,
        verbose_name=("Is connected"),
    )
    battery_percent = models.IntegerField(
        db_column="nb_battery_percent",
        default=0,
        verbose_name=("Battery percent"),
    )
    last_sync_at = models.DateTimeField(
        db_column="dt_last_sync_at",
        null=True,
        blank=True,
        verbose_name=("Last sync at"),
    )
    syncing = models.BooleanField(
        db_column="cs_syncing",
        default=False,
        verbose_name=("Syncing"),
    )

    history = HistoricalRecords(table_name='"history"."watch_device_status_history"')

    class Meta:
        ordering = ["-last_sync_at", "-id"]
        indexes = [
            models.Index(fields=["employee", "last_sync_at"]),
            models.Index(fields=["employee", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}:{self.device_name}"


class WearableSample(ModelBase):
    class SensorType(models.TextChoices):
        HR = "hr", "Heart Rate"
        EDA = "eda", "Electrodermal Activity"
        TEMP = "temp", "Temperature"
        ACC = "acc", "Accelerometer"
        BVP = "bvp", "Blood Volume Pulse"
        HRV = "hrv", "Heart Rate Variability"

    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="wearable_samples",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    device_id = models.CharField(
        db_column="tx_device_id",
        max_length=80,
        verbose_name=("Device ID"),
        help_text="Identificador do wearable na coleta.",
    )
    sensor_type = models.CharField(
        db_column="tx_sensor_type",
        max_length=16,
        choices=SensorType.choices,
        verbose_name=("Sensor type"),
    )
    recorded_at = models.DateTimeField(
        db_column="dt_recorded_at",
        verbose_name=("Recorded at"),
        help_text="Timestamp UTC da leitura no dispositivo.",
    )
    value = models.FloatField(
        db_column="nb_value",
        verbose_name=("Value"),
    )
    unit = models.CharField(
        db_column="tx_unit",
        max_length=20,
        blank=True,
        default="",
        verbose_name=("Unit"),
    )
    quality = models.FloatField(
        db_column="nb_quality",
        default=1.0,
        verbose_name=("Signal quality"),
        help_text="Qualidade da leitura em escala 0..1.",
    )
    payload = models.JSONField(
        db_column="js_payload",
        default=dict,
        blank=True,
        verbose_name=("Payload"),
        help_text="Campos opcionais da leitura bruta.",
    )

    history = HistoricalRecords(table_name='"history"."wearable_sample_history"')

    class Meta:
        ordering = ["-recorded_at", "-id"]
        indexes = [
            models.Index(fields=["employee", "recorded_at"]),
            models.Index(fields=["sensor_type", "recorded_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee.pk}:{self.sensor_type}@{self.recorded_at.isoformat()}"


class StressInferenceSnapshot(ModelBase):
    class StressRisk(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="stress_snapshots",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    window_start = models.DateTimeField(
        db_column="dt_window_start",
        verbose_name=("Window start"),
    )
    window_end = models.DateTimeField(
        db_column="dt_window_end",
        verbose_name=("Window end"),
    )
    stress_score = models.FloatField(
        db_column="nb_stress_score",
        verbose_name=("Stress score"),
        help_text="Score normalizado 0..1.",
    )
    risk_level = models.CharField(
        db_column="tx_risk_level",
        max_length=16,
        choices=StressRisk.choices,
        verbose_name=("Risk level"),
    )
    signal_quality = models.FloatField(
        db_column="nb_signal_quality",
        default=1.0,
        verbose_name=("Signal quality"),
        help_text="Qualidade agregada da janela em 0..1.",
    )
    model_version = models.CharField(
        db_column="tx_model_version",
        max_length=80,
        default="stress-heuristic-v1",
        verbose_name=("Model version"),
    )
    feature_summary = models.JSONField(
        db_column="js_feature_summary",
        default=dict,
        blank=True,
        verbose_name=("Feature summary"),
    )
    trigger_recommended = models.BooleanField(
        db_column="cs_trigger_recommended",
        default=False,
        verbose_name=("Trigger recommended"),
    )

    history = HistoricalRecords(table_name='"history"."stress_inference_snapshot_history"')

    class Meta:
        ordering = ["-window_end", "-id"]
        indexes = [
            models.Index(fields=["employee", "window_end"]),
            models.Index(fields=["risk_level", "window_end"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee.pk}:{self.stress_score:.2f} ({self.risk_level})"


class BurnoutAssessment(ModelBase):
    class AssessmentSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        TRIGGERED = "triggered", "Triggered by stress"
        SCHEDULED = "scheduled", "Scheduled"

    class BurnoutRisk(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="burnout_assessments",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    source = models.CharField(
        db_column="tx_source",
        max_length=16,
        choices=AssessmentSource.choices,
        default=AssessmentSource.MANUAL,
        verbose_name=("Source"),
    )
    answers = models.JSONField(
        db_column="js_answers",
        default=dict,
        verbose_name=("Answers"),
    )
    composite_score = models.FloatField(
        db_column="nb_composite_score",
        verbose_name=("Composite score"),
        help_text="Score composto de burnout 0..1.",
    )
    risk_level = models.CharField(
        db_column="tx_risk_level",
        max_length=16,
        choices=BurnoutRisk.choices,
        verbose_name=("Risk level"),
    )
    method_version = models.CharField(
        db_column="tx_method_version",
        max_length=80,
        default="burnout-composite-v1",
        verbose_name=("Method version"),
    )
    notes = models.TextField(
        db_column="tx_notes",
        blank=True,
        default="",
        verbose_name=("Notes"),
    )

    history = HistoricalRecords(table_name='"history"."burnout_assessment_history"')

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["employee", "created_at"])]

    def __str__(self) -> str:
        return f"{self.employee.pk}:{self.composite_score:.2f} ({self.risk_level})"


class RiskTriageDecision(ModelBase):
    class CombinedRisk(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    class InferenceMode(models.TextChoices):
        HYBRID = "hybrid", "Hybrid"
        ASSESSMENT_ONLY = "assessment_only", "Assessment Only"
        WEARABLE_ONLY = "wearable_only", "Wearable Only"

    class ConfidenceLevel(models.TextChoices):
        HIGH = "high", "High"
        MODERATE = "moderate", "Moderate"
        LOW = "low", "Low"

    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="risk_triage_decisions",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    stress_score = models.FloatField(
        db_column="nb_stress_score",
        default=0.0,
        verbose_name=("Stress score"),
    )
    burnout_score = models.FloatField(
        db_column="nb_burnout_score",
        default=0.0,
        verbose_name=("Burnout score"),
    )
    final_score = models.FloatField(
        db_column="nb_final_score",
        verbose_name=("Final score"),
    )
    risk_level = models.CharField(
        db_column="tx_risk_level",
        max_length=16,
        choices=CombinedRisk.choices,
        verbose_name=("Risk level"),
    )
    recommendation = models.CharField(
        db_column="tx_recommendation",
        max_length=180,
        verbose_name=("Recommendation"),
    )
    inference_mode = models.CharField(
        db_column="tx_inference_mode",
        max_length=24,
        choices=InferenceMode.choices,
        default=InferenceMode.HYBRID,
        verbose_name=("Inference mode"),
    )
    confidence_level = models.CharField(
        db_column="tx_confidence_level",
        max_length=16,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.MODERATE,
        verbose_name=("Confidence level"),
    )
    details = models.JSONField(
        db_column="js_details",
        default=dict,
        blank=True,
        verbose_name=("Details"),
    )

    history = HistoricalRecords(table_name='"history"."risk_triage_decision_history"')

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["employee", "created_at"])]

    def __str__(self) -> str:
        return f"{self.employee.pk}:{self.final_score:.2f} ({self.risk_level}/{self.inference_mode})"


class Recommendation(ModelBase):
    class Priority(models.TextChoices):
        LOW = "Baixa", "Baixa"
        MEDIUM = "Media", "Media"
        HIGH = "Alta", "Alta"

    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="recommendations",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=("Employee"),
    )
    title = models.CharField(
        db_column="tx_title",
        max_length=160,
        verbose_name=("Title"),
    )
    description = models.TextField(
        db_column="tx_description",
        verbose_name=("Description"),
    )
    reason = models.CharField(
        db_column="tx_reason",
        max_length=240,
        verbose_name=("Reason"),
    )
    priority = models.CharField(
        db_column="tx_priority",
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name=("Priority"),
    )

    history = HistoricalRecords(table_name='"history"."recommendation_history"')

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["employee", "active"]),
            models.Index(fields=["priority", "active"]),
        ]

    def __str__(self) -> str:
        return self.title


class Article(ModelBase):
    title = models.CharField(
        db_column="tx_title",
        max_length=180,
        verbose_name=("Title"),
    )
    category = models.CharField(
        db_column="tx_category",
        max_length=80,
        verbose_name=("Category"),
    )
    summary = models.TextField(
        db_column="tx_summary",
        blank=True,
        default="",
        verbose_name=("Summary"),
    )
    author = models.CharField(
        db_column="tx_author",
        max_length=120,
        blank=True,
        default="",
        verbose_name=("Author"),
    )
    read_time_minutes = models.IntegerField(
        db_column="nb_read_time_minutes",
        default=1,
        verbose_name=("Read time minutes"),
    )
    watch_summary = models.CharField(
        db_column="tx_watch_summary",
        max_length=240,
        blank=True,
        default="",
        verbose_name=("Watch summary"),
    )

    history = HistoricalRecords(table_name='"history"."article_history"')

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["category", "active"]),
        ]

    def __str__(self) -> str:
        return self.title


class ArticleSection(ModelBase):
    article = models.ForeignKey(
        "employee.Article",
        db_column="id_article",
        related_name="sections",
        on_delete=models.CASCADE,
        verbose_name=("Article"),
    )
    heading = models.CharField(
        db_column="tx_heading",
        max_length=160,
        verbose_name=("Heading"),
    )
    body = models.TextField(
        db_column="tx_body",
        verbose_name=("Body"),
    )
    order = models.PositiveIntegerField(
        db_column="nb_order",
        default=0,
        verbose_name=("Order"),
    )

    history = HistoricalRecords(table_name='"history"."article_section_history"')

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["article", "order"])]

    def __str__(self) -> str:
        return f"{self.article_id}:{self.heading}"


class MobileNotification(ModelBase):
    employee = models.ForeignKey(
        "employee.EmployeeRecord",
        db_column="id_employee_record",
        related_name="mobile_notifications",
        on_delete=models.CASCADE,
        verbose_name=("Employee"),
    )
    category = models.CharField(
        db_column="tx_category",
        max_length=80,
        verbose_name=("Category"),
    )
    title = models.CharField(
        db_column="tx_title",
        max_length=160,
        verbose_name=("Title"),
    )
    description = models.TextField(
        db_column="tx_description",
        verbose_name=("Description"),
    )
    occurred_at = models.DateTimeField(
        db_column="dt_occurred_at",
        verbose_name=("Occurred at"),
    )
    read_at = models.DateTimeField(
        db_column="dt_read_at",
        null=True,
        blank=True,
        verbose_name=("Read at"),
    )

    history = HistoricalRecords(table_name='"history"."mobile_notification_history"')

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["employee", "occurred_at"]),
            models.Index(fields=["employee", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}:{self.title}"
