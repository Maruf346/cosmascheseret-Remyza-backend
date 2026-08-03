from django.contrib import admin

from .models import (
    Organization,
    BusinessLink,
    BusinessAddress,
    BusinessSetting,
    ProviderAccount,
    PhoneNumber,
    LocalVerification,
    UserNotificationSettings,
)


class BusinessLinkInline(admin.TabularInline):
    model = BusinessLink
    extra = 0


class BusinessAddressInline(admin.TabularInline):
    model = BusinessAddress
    extra = 0

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "business_type", "industry", "country", "status", "has_phone_number_display", "primary_phone_display", "lead_count_display", "is_verified", "is_demo", "is_onboarding_completed", "created_at")
    list_filter = ("status", "country", "business_type", "industry", "is_verified", "is_demo", "is_onboarding_completed", "created_at")
    search_fields = ("name", "email", "support_email", "website", "owner__phone_number", "owner__email")
    autocomplete_fields = ("owner",)
    list_select_related = ("owner",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25
    fieldsets = (
        ("Organization Information", {"fields": ("owner", "name", "status", "country", "logo", "favicon")}),
        ("Business Information", {"fields": ("business_type", "industry", "description", "website", "email", "support_email", "business_hours")}),
        ("Onboarding", {"fields": ("is_verified", "is_demo", "is_onboarding_completed", "onboarding_step")}),
        ("System Information", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="Has Phone")
    def has_phone_number_display(self, obj):
        return obj.has_phone_number

    @admin.display(description="Primary Phone")
    def primary_phone_display(self, obj):
        phone = obj.primary_phone
        if phone:
            return phone.phone_number
        return "-"

    @admin.display(description="Leads")
    def lead_count_display(self, obj):
        return obj.lead_count


@admin.register(BusinessSetting)
class BusinessSettingAdmin(admin.ModelAdmin):
    list_display = ("organization", "language", "timezone", "currency", "reply_tone", "auto_reply_enabled")
    list_filter = ("language", "currency", "auto_reply_enabled")
    search_fields = ("organization__name",)
    autocomplete_fields = ("organization",)
    list_select_related = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProviderAccount)
class ProviderAccountAdmin(admin.ModelAdmin):
    list_display = ("organization", "provider", "friendly_name", "status", "last_synced_at")
    list_filter = ("provider", "status")
    search_fields = ("friendly_name", "account_sid", "organization__name")
    autocomplete_fields = ("organization",)
    list_select_related = ("organization",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "organization", "provider", "country", "status", "is_primary", "last_synced_at")
    list_filter = ("status", "country", "is_primary")
    search_fields = ("phone_number", "provider_phone_sid", "organization__name")
    autocomplete_fields = ("organization", "provider")
    list_select_related = ("organization", "provider")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

admin.site.register(LocalVerification)
# @admin.register(LocalVerification)

@admin.register(UserNotificationSettings)
class UserNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "organization", "all_notification", "push_notification_enabled", "email_alert_enabled", "sms_alert_enabled", "instant_lead_alert", "weekly_performance_report", "created_at")
    list_filter = ("all_notification", "push_notification_enabled", "email_alert_enabled", "sms_alert_enabled", "instant_lead_alert", "weekly_performance_report", "created_at")
    search_fields = ("user__phone_number", "user__email", "user__full_name", "organization__name")
    autocomplete_fields = ("user", "organization")
    list_select_related = ("user", "organization")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25

