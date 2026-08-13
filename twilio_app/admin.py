from django.contrib import admin

from .models import (
    CustomerProfile,
    BusinessEndUser,
    BusinessAddress,
    TrustHubEntityAssignment,
    A2PProfile,
    TrustHubEvaluation,
    A2PBrand,
    A2PCampaign,
    MessagingService,
    LocalVerification,
    LocalVerificationStep,
    TollFreeVerification,
    TwilioRequestLog,
    TwilioWebhookLog,
)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "profile_sid", "friendly_name", "status", "email",
        "submitted_at", "approved_at", "last_synced_at", "created_at",
    )
    list_filter = ("status", "created_at", "updated_at", "submitted_at", "approved_at")
    search_fields = (
        "organization__name", "profile_sid", "policy_sid", "friendly_name",
        "email", "failure_reason",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(BusinessEndUser)
class BusinessEndUserAdmin(admin.ModelAdmin):
    list_display = (
        "business_name", "organization", "end_user_sid", "end_user_type",
        "business_type", "business_industry", "status", "last_synced_at", "created_at",
    )
    list_filter = ("status", "business_type", "business_industry", "created_at", "updated_at")
    search_fields = (
        "business_name", "organization__name", "end_user_sid", "friendly_name",
        "business_registration_number", "business_registration_identifier",
        "website_url", "failure_reason",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("organization", "customer_profile")
    ordering = ("-created_at",)


@admin.register(BusinessAddress)
class BusinessAddressAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "customer_name", "street", "city", "state",
        "postal_code", "country", "twilio_sid", "last_synced_at", "created_at",
    )
    list_filter = ("country", "state", "city", "created_at", "updated_at")
    search_fields = (
        "organization__name", "customer_name", "friendly_name", "twilio_sid",
        "street", "street_secondary", "city", "state", "postal_code",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("organization",)
    ordering = ("-created_at",)


@admin.register(TrustHubEntityAssignment)
class TrustHubEntityAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "object_sid", "object_type", "assignment_sid", "status",
        "customer_profile", "a2p_profile", "assigned_at", "created_at",
    )
    list_filter = ("status", "object_type", "assigned_at", "created_at")
    search_fields = (
        "object_sid", "assignment_sid", "object_type", "status",
        "customer_profile__profile_sid", "a2p_profile__profile_sid",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("customer_profile", "a2p_profile")
    ordering = ("-created_at",)


@admin.register(A2PProfile)
class A2PProfileAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "profile_sid", "friendly_name", "status", "email",
        "submitted_at", "approved_at", "last_synced_at", "created_at",
    )
    list_filter = ("status", "created_at", "updated_at", "submitted_at", "approved_at")
    search_fields = (
        "organization__name", "profile_sid", "policy_sid", "friendly_name",
        "email", "failure_reason",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(TrustHubEvaluation)
class TrustHubEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "evaluation_sid", "policy_sid", "status", "customer_profile",
        "a2p_profile", "evaluated_at", "created_at",
    )
    list_filter = ("status", "evaluated_at", "created_at", "updated_at")
    search_fields = (
        "evaluation_sid", "policy_sid", "failure_reason",
        "customer_profile__profile_sid", "a2p_profile__profile_sid",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("customer_profile", "a2p_profile")
    ordering = ("-created_at",)


@admin.register(A2PBrand)
class A2PBrandAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "brand_sid", "brand_type", "status", "identity_status",
        "customer_profile", "a2p_profile", "submitted_at", "approved_at",
        "last_synced_at", "created_at",
    )
    list_filter = (
        "brand_type", "status", "identity_status", "created_at", "updated_at",
        "submitted_at", "approved_at",
    )
    search_fields = (
        "organization__name", "brand_sid", "customer_profile__profile_sid",
        "a2p_profile__profile_sid", "identity_status", "failure_reason",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("organization", "customer_profile", "a2p_profile")
    ordering = ("-created_at",)


@admin.register(A2PCampaign)
class A2PCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "campaign_sid", "brand", "campaign_type", "use_case",
        "status", "submitted_at", "approved_at", "last_synced_at", "created_at",
    )
    list_filter = (
        "status", "campaign_type", "use_case", "created_at", "updated_at",
        "submitted_at", "approved_at",
    )
    search_fields = (
        "organization__name", "campaign_sid", "brand__brand_sid",
        "campaign_type", "use_case", "description", "message_flow",
        "failure_reason",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("organization", "brand")
    ordering = ("-created_at",)


@admin.register(MessagingService)
class MessagingServiceAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "service_sid", "friendly_name", "status",
        "last_synced_at", "created_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = (
        "organization__name", "service_sid", "messaging_service_sid",
        "friendly_name",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("organization",)
    ordering = ("-created_at",)

@admin.register(LocalVerification)
class LocalVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "phone_number", "status", "current_step",
        "complete_progress", "messaging_service", "a2p_brand", "a2p_campaign",
        "started_at", "completed_at", "last_synced_at", "created_at",
    )
    list_filter = (
        "status", "current_step", "created_at", "updated_at",
        "started_at", "completed_at",
    )
    search_fields = (
        "organization__name", "phone_number__phone_number", "current_step",
        "failure_reason", "last_error", "messaging_service__service_sid",
        "a2p_brand__brand_sid", "a2p_campaign__campaign_sid",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "organization", "phone_number", "messaging_service",
        "a2p_brand", "a2p_campaign",
    )
    ordering = ("-created_at",)


@admin.register(LocalVerificationStep)
class LocalVerificationStepAdmin(admin.ModelAdmin):
    list_display = (
        "verification", "step", "status", "retry_count",
        "started_at", "completed_at", "created_at",
    )
    list_filter = ("step", "status", "created_at", "updated_at")
    search_fields = (
        "verification__organization__name",
        "verification__phone_number__phone_number",
        "verification__current_step", "step", "error_message",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("verification",)
    ordering = ("-created_at",)


@admin.register(TollFreeVerification)
class TollFreeVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "business_name", "organization", "phone_number",
        "free_trail_phone_number", "verification_sid", "verification_status",
        "is_verified", "submitted_at", "approved_at", "rejected_at", "created_at",
    )
    list_filter = (
        "verification_status", "is_verified", "business_type",
        "business_registration_authority", "opt_in_type", "age_gated_content",
        "created_at", "updated_at", "submitted_at", "approved_at", "rejected_at",
    )
    search_fields = (
        "business_name", "doing_business_as", "organization__name",
        "user__email", "customer_profile_sid", "tollfree_phone_number_sid",
        "verification_sid", "external_reference_id",
        "business_registration_number", "business_registration_phone_number",
        "business_website", "notification_email", "rejection_reason",
        "rejection_reasons", "rejection_code",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "organization", "user", "phone_number", "free_trail_phone_number",
    )
    ordering = ("-created_at",)


@admin.register(TwilioRequestLog)
class TwilioRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "organization", "verification", "operation", "method",
        "twilio_sid", "status_code", "success", "duration_ms", "created_at",
    )
    list_filter = ("success", "method", "status_code", "operation", "created_at")
    search_fields = (
        "organization__name", "operation", "endpoint", "twilio_sid",
        "error_message", "verification__phone_number__phone_number",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("organization", "verification")
    ordering = ("-created_at",)


@admin.register(TwilioWebhookLog)
class TwilioWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("method", "path", "ip_address", "created_at")
    list_filter = ("method", "created_at")
    search_fields = ("path", "ip_address", "body")
    readonly_fields = ("created_at", "headers", "payload", "body")
    ordering = ("-created_at",)

