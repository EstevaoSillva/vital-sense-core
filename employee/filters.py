import django_filters

from .models import EmployeeRecord


class EmployeeRecordFilter(django_filters.FilterSet):
    user = django_filters.NumberFilter(field_name="user_id")
    enterprise = django_filters.NumberFilter(field_name="enterprise_id")
    username = django_filters.CharFilter(field_name="user__username", lookup_expr="icontains")
    email = django_filters.CharFilter(field_name="user__email", lookup_expr="icontains")
    name = django_filters.CharFilter(field_name="user__name", lookup_expr="icontains")
    enterprise_name = django_filters.CharFilter(field_name="enterprise__name", lookup_expr="icontains")

    class Meta:
        model = EmployeeRecord
        fields = (
            "id",
            "user",
            "enterprise",
            "username",
            "email",
            "name",
            "enterprise_name",
            "active",
        )
