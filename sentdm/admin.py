from django.contrib import admin

from .models import SentDMCampaign, SentDMMessage, SentDMProfile, SentDMWebhookEvent


@admin.register(SentDMProfile)
class SentDMProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "profile_id", "status", "phone_number", "sandbox", "created_at")
    list_filter = ("status", "sandbox", "billing_model")
    search_fields = ("name", "profile_id", "phone_number", "email")
    readonly_fields = ("created_at", "updated_at", "last_synced_at")



@admin.register(SentDMCampaign)
class SentDMCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "campaign_id", "profile", "status", "submitted_to_tcr", "sandbox", "created_at")
    list_filter = ("status", "submitted_to_tcr", "sandbox", "campaign_type", "messaging_use_case_us")
    search_fields = ("name", "campaign_id", "profile__profile_id", "organization__name")
    readonly_fields = ("created_at", "updated_at", "last_synced_at")

@admin.register(SentDMMessage)
class SentDMMessageAdmin(admin.ModelAdmin):
    list_display = ("sent_message_id", "direction", "channel", "status", "to_number", "sandbox", "created_at")
    list_filter = ("direction", "channel", "status", "sandbox")
    search_fields = ("sent_message_id", "from_number", "to_number", "body")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SentDMWebhookEvent)
class SentDMWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "profile_id", "signature_verified", "status", "created_at")
    list_filter = ("event_type", "signature_verified", "status")
    search_fields = ("event_id", "event_type", "profile_id")
    readonly_fields = ("created_at", "updated_at", "processed_at")

