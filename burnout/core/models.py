from django.db import models


class ModelBase(models.Model):
    id = models.BigAutoField(
        db_column='id',
        null=False,
        primary_key=True,
        verbose_name=('Id')
    )
    created_at = models.DateTimeField(
        db_column='dt_created_at',
        auto_now_add=True,
        null=True,
        verbose_name=('Created at')
    )
    modified_at = models.DateTimeField(
        db_column='dt_modified_at',
        auto_now=True,
        null=True,
        verbose_name=('Modified at')
    )
    active = models.BooleanField(
        db_column='cs_active',
        null=False,
        default=True,
        verbose_name=('Active'),
    )

    class Meta:
        abstract = True
        managed = True
        default_permissions = ("add", "change", "delete", "view")
