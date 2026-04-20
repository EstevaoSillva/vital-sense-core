from django.contrib import admin

from .models import (
    BurnoutAssessment,
    EmployeeRecord,
    RiskTriageDecision,
    StressInferenceSnapshot,
    WearableSample,
)


@admin.register(EmployeeRecord)
class EmployeeRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "enterprise",
        "active",
        "created_at",
        "modified_at",
    )
    search_fields = ("=id", "user__username", "user__email", "user__name", "enterprise__name", "enterprise__code")
    list_filter = ("active", "enterprise")


@admin.register(WearableSample)
class WearableSampleAdmin(admin.ModelAdmin):
    list_display = ("employee", "device_id", "sensor_type", "value", "quality", "recorded_at")
    search_fields = ("=employee__id", "employee__user__username", "device_id")
    list_filter = ("sensor_type",)
    ordering = ("-recorded_at",)


@admin.register(StressInferenceSnapshot)
class StressInferenceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("employee", "stress_score", "risk_level", "signal_quality", "window_end", "trigger_recommended")
    search_fields = ("=employee__id", "employee__user__username")
    list_filter = ("risk_level", "trigger_recommended")
    ordering = ("-window_end",)


@admin.register(BurnoutAssessment)
class BurnoutAssessmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "source", "composite_score", "risk_level", "created_at")
    search_fields = ("=employee__id", "employee__user__username")
    list_filter = ("source", "risk_level")
    ordering = ("-created_at",)


@admin.register(RiskTriageDecision)
class RiskTriageDecisionAdmin(admin.ModelAdmin):
    list_display = ("employee", "stress_score", "burnout_score", "final_score", "risk_level", "created_at")
    search_fields = ("=employee__id", "employee__user__username")
    list_filter = ("risk_level",)
    ordering = ("-created_at",)
