from django.contrib import admin

from .models import EnterpriseCommercialProfile, TherapyGroup, TherapyGroupMember


@admin.register(EnterpriseCommercialProfile)
class EnterpriseCommercialProfileAdmin(admin.ModelAdmin):
    list_display = ("enterprise", "company_size", "plan_id", "active")
    search_fields = ("enterprise__name", "enterprise__code", "tax_id", "contact_email")
    list_filter = ("plan_id", "active")


@admin.register(TherapyGroup)
class TherapyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "enterprise", "status", "facilitator_name", "next_session_at", "active")
    search_fields = ("name", "focus", "enterprise__name", "enterprise__code")
    list_filter = ("status", "active")


@admin.register(TherapyGroupMember)
class TherapyGroupMemberAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "active")
    search_fields = ("group__name", "user__username", "user__email", "user__name")
    list_filter = ("active",)
