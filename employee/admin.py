from django.contrib import admin

from .models import (
    Article,
    ArticleSection,
    BurnoutAssessment,
    EmployeeProfile,
    EmployeeRecord,
    MobileNotification,
    Recommendation,
    RiskTriageDecision,
    StressInferenceSnapshot,
    WatchDeviceStatus,
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


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("employee", "job_title", "work_schedule", "active")
    search_fields = ("=employee__id", "employee__user__username", "job_title")
    list_filter = ("active",)


@admin.register(WatchDeviceStatus)
class WatchDeviceStatusAdmin(admin.ModelAdmin):
    list_display = ("employee", "device_name", "is_connected", "battery_percent", "last_sync_at", "syncing")
    search_fields = ("=employee__id", "employee__user__username", "device_name")
    list_filter = ("is_connected", "syncing", "active")
    ordering = ("-last_sync_at",)


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


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("title", "employee", "priority", "active", "created_at")
    search_fields = ("title", "description", "reason", "employee__user__username")
    list_filter = ("priority", "active")
    ordering = ("-created_at",)


class ArticleSectionInline(admin.TabularInline):
    model = ArticleSection
    extra = 1


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "read_time_minutes", "active", "created_at")
    search_fields = ("title", "category", "summary", "author")
    list_filter = ("category", "active")
    ordering = ("-created_at",)
    inlines = (ArticleSectionInline,)


@admin.register(MobileNotification)
class MobileNotificationAdmin(admin.ModelAdmin):
    list_display = ("employee", "category", "title", "occurred_at", "active")
    search_fields = ("=employee__id", "employee__user__username", "title", "description")
    list_filter = ("category", "active")
    ordering = ("-occurred_at",)
