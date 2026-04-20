from django.db import models
from simple_history.models import HistoricalRecords

from core.models import ModelBase


class Enterprise(ModelBase):
    name = models.CharField(
        db_column="tx_name",
        max_length=255,
        verbose_name="Name",
    )
    code = models.CharField(
        db_column="tx_code",
        max_length=100,
        verbose_name="Code",
        help_text="Codigo unico da unidade organizacional.",
    )
    kind = models.CharField(
        db_column="tx_kind",
        max_length=50,
        default="unit",
        verbose_name="Kind",
    )

    history = HistoricalRecords(table_name='"history"."enterprise_history"')

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["code"], name="uq_enterprise_code")]
        indexes = [
            models.Index(fields=["active"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}:{self.name}"
