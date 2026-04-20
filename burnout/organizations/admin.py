from django.contrib import admin

from .models import Enterprise


@admin.register(Enterprise)
class EnterpriseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "kind", "active", "created_at")
    search_fields = ("name", "code")
    list_filter = ("kind", "active")
