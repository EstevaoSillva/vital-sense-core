from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from core.models import ModelBase


class EnterpriseCommercialProfile(ModelBase):
    enterprise = models.OneToOneField(
        "organizations.Enterprise",
        db_column="id_enterprise",
        related_name="commercial_profile",
        on_delete=models.CASCADE,
        verbose_name="Enterprise",
    )
    tax_id = models.CharField(db_column="tx_tax_id", max_length=32, blank=True, default="", verbose_name="Tax ID")
    contact_name = models.CharField(
        db_column="tx_contact_name",
        max_length=160,
        blank=True,
        default="",
        verbose_name="Contact name",
    )
    contact_email = models.EmailField(
        db_column="tx_contact_email",
        max_length=256,
        blank=True,
        default="",
        verbose_name="Contact email",
    )
    company_size = models.CharField(
        db_column="tx_company_size",
        max_length=40,
        blank=True,
        default="",
        verbose_name="Company size",
    )
    plan_id = models.CharField(db_column="tx_plan_id", max_length=40, blank=True, default="", verbose_name="Plan ID")

    history = HistoricalRecords(table_name='"history"."enterprise_commercial_profile_history"')

    class Meta:
        ordering = ["enterprise_id"]
        indexes = [models.Index(fields=["enterprise", "active"])]

    def __str__(self) -> str:
        return f"{self.enterprise_id}:{self.plan_id or 'no-plan'}"


class TherapyGroup(ModelBase):
    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        INVITED = "invited", "Invited"
        SCHEDULED = "scheduled", "Scheduled"

    enterprise = models.ForeignKey(
        "organizations.Enterprise",
        db_column="id_enterprise",
        related_name="therapy_groups",
        on_delete=models.CASCADE,
        verbose_name="Enterprise",
    )
    name = models.CharField(db_column="tx_name", max_length=160, verbose_name="Name")
    focus = models.CharField(db_column="tx_focus", max_length=180, verbose_name="Focus")
    status = models.CharField(
        db_column="tx_status",
        max_length=24,
        choices=Status.choices,
        default=Status.SUGGESTED,
        verbose_name="Status",
    )
    facilitator_name = models.CharField(
        db_column="tx_facilitator_name",
        max_length=160,
        blank=True,
        default="",
        verbose_name="Facilitator name",
    )
    next_session_at = models.DateTimeField(
        db_column="dt_next_session_at",
        null=True,
        blank=True,
        verbose_name="Next session at",
    )

    history = HistoricalRecords(table_name='"history"."therapy_group_history"')

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["enterprise", "active"]),
            models.Index(fields=["status", "active"]),
        ]

    def __str__(self) -> str:
        return self.name


class TherapyGroupMember(ModelBase):
    group = models.ForeignKey(
        "enterprise.TherapyGroup",
        db_column="id_therapy_group",
        related_name="memberships",
        on_delete=models.CASCADE,
        verbose_name="Therapy group",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_user",
        related_name="therapy_group_memberships",
        on_delete=models.CASCADE,
        verbose_name="User",
    )

    history = HistoricalRecords(table_name='"history"."therapy_group_member_history"')

    class Meta:
        ordering = ["group_id", "user_id"]
        constraints = [models.UniqueConstraint(fields=["group", "user"], name="uq_therapy_group_member")]
        indexes = [
            models.Index(fields=["group", "active"]),
            models.Index(fields=["user", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.group_id}:{self.user_id}"
