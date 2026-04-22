from django.contrib import admin

from .models import AccountUserGroup, RecoveryPassword, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "name", "is_active", "is_staff", "external", "created_at")
    search_fields = ("username", "email", "name", "desired_name")
    list_filter = ("is_active", "is_staff", "is_superuser", "external", "regime", "last_login_language")


@admin.register(AccountUserGroup)
class AccountUserGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "group", "active", "created_at")
    search_fields = ("user__username", "user__email", "group__name")
    list_filter = ("active", "group")


@admin.register(RecoveryPassword)
class RecoveryPasswordAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "code", "expiration_date", "checked_date", "active", "created_at")
    search_fields = ("user__username", "user__email", "code")
    list_filter = ("active", "checked_date")
