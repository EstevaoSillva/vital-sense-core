from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Group, PermissionsMixin
from django.db import models
from django.db.models import Q

from core.models import ModelBase

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The username must be set")
        username = self.model.normalize_username(username)
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Regime(models.TextChoices):
        HOME_OFFICE = "0", "Home office"
        HYBRID = "1", "Hybrid"
        LOCAL = "2", "Local"

    class Language(models.TextChoices):
        PT_BR = "pt-BR", "Portuguese (Brazil)"
        EN_US = "en-US", "English (US)"

    id = models.BigAutoField(db_column="id", primary_key=True, verbose_name="Id")
    created_at = models.DateTimeField(
        db_column="dt_created_at",
        auto_now_add=True,
        null=True,
        verbose_name="Created at",
    )
    modified_at = models.DateTimeField(
        db_column="dt_modified_at",
        auto_now=True,
        null=True,
        verbose_name="Modified at",
    )
    username = models.CharField(
        db_column="tx_username",
        max_length=64,
        verbose_name="Username",
    )
    email = models.EmailField(
        db_column="tx_email",
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Email",
    )
    name = models.CharField(
        db_column="tx_name",
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Name",
    )
    desired_name = models.CharField(
        db_column="tx_desired_name",
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Desired name",
    )
    check_show_again = models.BooleanField(
        db_column="cs_check_show_again",
        default=True,
        verbose_name="Check show again",
    )
    last_login_language = models.CharField(
        db_column="tx_last_login_language",
        max_length=5,
        choices=Language.choices,
        null=True,
        blank=True,
        verbose_name="Last login language",
    )
    is_active = models.BooleanField(
        db_column="cs_active",
        default=True,
        verbose_name="Active",
    )
    is_staff = models.BooleanField(
        db_column="cs_staff",
        default=False,
        verbose_name="Staff status",
    )
    is_default = models.BooleanField(
        db_column="cs_default",
        default=False,
        verbose_name="Default user",
    )
    regime = models.CharField(
        db_column="cs_regime",
        max_length=1,
        choices=Regime.choices,
        default=Regime.HOME_OFFICE,
        null=True,
        blank=True,
        verbose_name="Regime",
    )
    admission_date = models.DateField(
        db_column="dt_admission_date",
        null=True,
        blank=True,
        verbose_name="Admission date",
    )
    birth_date = models.DateField(
        db_column="dt_birth_date",
        null=True,
        blank=True,
        verbose_name="Birth date",
    )
    resignation_date = models.DateField(
        db_column="dt_resignation_date",
        null=True,
        blank=True,
        verbose_name="Resignation date",
    )
    cpf = models.CharField(
        db_column="tx_cpf",
        max_length=11,
        null=True,
        blank=True,
        verbose_name="CPF",
    )
    github = models.CharField(
        db_column="tx_github",
        max_length=1024,
        null=True,
        blank=True,
        verbose_name="GitHub",
    )
    linkedin = models.CharField(
        db_column="tx_linkedin",
        max_length=1024,
        null=True,
        blank=True,
        verbose_name="LinkedIn",
    )
    external = models.BooleanField(
        db_column="cs_user_is_external",
        default=False,
        verbose_name="External user",
    )
    groups = models.ManyToManyField(
        Group,
        through="accounts.AccountUserGroup",
        blank=True,
        verbose_name="groups",
        help_text="The groups this user belongs to.",
        related_name="user_set",
        related_query_name="user",
    )
    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["username"]
        constraints = [
            models.UniqueConstraint(fields=["username"], name="uq_user_username"),
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(email__isnull=False) & ~Q(email=""),
                name="uq_user_email_not_null",
            ),
        ]
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["is_active", "is_staff"]),
        ]

    def __str__(self) -> str:
        return self.name or self.username

    def get_full_name(self) -> str:
        return self.name or self.username

    def get_short_name(self) -> str:
        return self.desired_name or self.name or self.username


class AccountUserGroup(ModelBase):
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.DO_NOTHING,
        db_column="id_user",
        related_name="account_user_groups",
        verbose_name="User",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.DO_NOTHING,
        db_column="id_group",
        related_name="account_user_groups",
        verbose_name="Group",
    )

    class Meta:
        db_table = "account_user_groups"
        constraints = [
            models.UniqueConstraint(fields=["user", "group"], name="uq_account_user_group"),
        ]
        indexes = [
            models.Index(fields=["user", "active"]),
            models.Index(fields=["group", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.group_id}"


class RecoveryPassword(ModelBase):
    code = models.SlugField(
        db_column="tx_code",
        max_length=6,
        verbose_name="Code",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.DO_NOTHING,
        db_column="id_user",
        related_name="recovery_passwords",
        verbose_name="User",
    )
    expiration_date = models.DateTimeField(
        db_column="dt_expiration_date",
        verbose_name="Expiration date",
    )
    checked_date = models.BooleanField(
        db_column="cs_checked_date",
        null=True,
        blank=True,
        verbose_name="Checked date",
    )

    class Meta:
        db_table = "account_code"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "active"]),
            models.Index(fields=["code", "active"]),
            models.Index(fields=["expiration_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.code}"
