import django_filters

from .models import AccountUserGroup, RecoveryPassword, User


class UserFilter(django_filters.FilterSet):
    username = django_filters.CharFilter(field_name="username", lookup_expr="icontains")
    email = django_filters.CharFilter(field_name="email", lookup_expr="icontains")
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    is_active = django_filters.BooleanFilter(field_name="is_active")
    is_staff = django_filters.BooleanFilter(field_name="is_staff")
    external = django_filters.BooleanFilter(field_name="external")

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "name",
            "is_active",
            "is_staff",
            "is_superuser",
            "external",
        )


class AccountUserGroupFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(field_name="user_id")
    group = django_filters.NumberFilter(field_name="group_id")
    active = django_filters.BooleanFilter(field_name="active")

    class Meta:
        model = AccountUserGroup
        fields = ("id", "user", "group", "active")


class RecoveryPasswordFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(field_name="user_id")
    code = django_filters.CharFilter(field_name="code", lookup_expr="icontains")
    active = django_filters.BooleanFilter(field_name="active")

    class Meta:
        model = RecoveryPassword
        fields = ("id", "user", "code", "active")
