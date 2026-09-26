from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Device,
    OTPVerification,
    LoginHistory,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "phone_number", "email", "full_name", "city", "country", "is_phone_verified", "is_staff", "is_superuser", "status", "last_activity_at", "created_at")
    list_filter = ("is_staff", "is_superuser", "is_phone_verified", "status", "created_at")
    search_fields = ("phone_number", "email", "full_name", "city", "country")
    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"
    readonly_fields = ("last_login", "last_activity_at", "last_password_changed_at", "created_at", "updated_at")
    fieldsets = (
        ("Basic Information", {"fields": ("phone_number", "email", "full_name", "city", "country", "country_code", "profile_picture")}),
        ("Verification", {"fields": ("is_phone_verified",)}),
        ("Authentication", {"fields": ("password", "last_login", "failed_login_attempts", "last_password_changed_at")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("System", {"fields": ("status", "last_activity_at", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("phone_number", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "device_name", "device_type", "manufacturer", "model", "app_version", "is_active", "last_seen_at")
    list_filter = ("device_type", "is_active", "created_at")
    search_fields = ("device_name", "device_id", "manufacturer", "model", "user__phone_number", "user__email")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    readonly_fields = ("last_seen_at", "created_at", "updated_at")
    ordering = ("-last_seen_at",)
    date_hierarchy = "last_seen_at"
    list_per_page = 25

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "otp_code", "phone_number", "purpose", "attempt_count", "is_used", "expires_at", "verified_at", "created_at")
    list_filter = ("purpose", "is_used", "created_at")
    search_fields = ("phone_number", "user__phone_number", "user__email")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    readonly_fields = ("otp_hash", "verified_at", "created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone_number", "login_method", "status", "device", "ip_address", "created_at")
    list_filter = ("login_method", "status", "created_at")
    search_fields = ("phone_number", "ip_address", "failure_reason", "user__phone_number", "user__email", "device__device_name")
    autocomplete_fields = ("user", "device")
    list_select_related = ("user", "device")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25
    
    readonly_fields = [field.name for field in LoginHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

