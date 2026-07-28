from django.contrib import admin
from .models import (
    BusinessType, Notification, AuditLog, SystemSetting, APIKey, Industry,
    TwilioConfiguration, FreeTrailPhoneNumber, UserFreeTrailNumber, TwilioWebhookLog, TollFreeVerification
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


@admin.register(TwilioConfiguration)
class TwilioConfigurationAdmin(admin.ModelAdmin):
    list_display = ("id", "default_country", "enable_trial", "auto_create_subaccount", "auto_purchase_number", "is_active", "last_synced_at")
    list_filter = ("enable_trial", "auto_create_subaccount", "auto_purchase_number", "is_active")
    search_fields = ("master_account_sid", "trial_account_sid")
    readonly_fields = ("last_synced_at", "created_at", "updated_at")
    list_per_page = 25


@admin.register(FreeTrailPhoneNumber)
class FreeTrailPhoneNumberAdmin(admin.ModelAdmin):
    list_display = ("id", "phone_number", "number_type", "account_sid", "is_used", "status", "purchased_at")
    list_filter = ("number_type", "status", "is_used")
    search_fields = ("phone_number", "provider_phone_sid", "account_sid")
    readonly_fields = ("provider_phone_sid", "purchased_at", "released_at", "last_synced_at", "created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25


@admin.register(UserFreeTrailNumber)
class UserFreeTrailNumberAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "free_trail", "trail_number", "start_at", "end_at", "is_expired")
    list_filter = ("is_expired",)
    search_fields = ("organization__name", "trail_number")
    autocomplete_fields = ("organization", "free_trail")
    list_select_related = ("organization", "free_trail")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-start_at",)
    date_hierarchy = "start_at"
    list_per_page = 25


@admin.register(TollFreeVerification)
class TollFreeVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "phone_number", "organization", "business_name", "verification_status", "is_verified", "submitted_at", "approved_at")
    list_filter = ("verification_status", "is_verified", "opt_in_type", "age_gated_content")
    search_fields = ("business_name", "verification_sid", "customer_profile_sid", "notification_email")
    autocomplete_fields = ("phone_number", "free_trail_phone_number", "organization", "user")
    list_select_related = ("phone_number", "free_trail_phone_number", "organization", "user")
    readonly_fields = ("verification_sid", "submitted_at", "approved_at", "rejected_at", "last_synced_at", "created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25


@admin.register(TwilioWebhookLog)
class TwilioWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("id", "method", "path", "ip_address", "created_at")
    search_fields = ("path", "method", "ip_address")
    readonly_fields = [field.name for field in TwilioWebhookLog._meta.fields]
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request):
        return False
