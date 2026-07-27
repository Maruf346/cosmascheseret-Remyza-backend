from django.contrib import admin

from .models import (
    BusinessType, Notification, AuditLog, SystemSetting, APIKey, Industry,
    TwilioConfiguration, FreeTrailPhoneNumber, UserFreeTrailNumber, TwilioWebhookLog
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "organization", "notification_type", "priority", "is_read", "sent_at", "created_at")
    list_filter = ("notification_type", "priority", "is_read", "created_at")
    search_fields = ("title", "body", "user__phone_number", "user__email", "organization__name")
    autocomplete_fields = ("user", "organization")
    list_select_related = ("user", "organization")
    readonly_fields = ("sent_at", "read_at", "created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "user", "module", "action", "object_type", "request_method", "ip_address", "created_at")
    list_filter = ("module", "request_method", "created_at")
    search_fields = ("action", "module", "object_type", "request_path", "user__phone_number", "user__email", "organization__name")
    autocomplete_fields = ("organization", "user")
    list_select_related = ("organization", "user")
    readonly_fields = [field.name for field in AuditLog._meta.fields]
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "value_type", "is_public", "created_at")
    list_filter = ("value_type", "is_public", "created_at")
    search_fields = ("key", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("key",)
    list_per_page = 25


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization", "is_active", "last_used_at", "expires_at", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "api_key", "organization__name")
    autocomplete_fields = ("organization",)
    list_select_related = ("organization",)
    readonly_fields = ("api_key", "secret_key", "last_used_at", "created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25



admin.site.register(BusinessType)
admin.site.register(Industry)
admin.site.register(TwilioConfiguration)
admin.site.register(FreeTrailPhoneNumber)
admin.site.register(UserFreeTrailNumber)
admin.site.register(TwilioWebhookLog)
