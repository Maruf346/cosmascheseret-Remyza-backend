from django.db import models
from django.utils import timezone

from common.models import BaseModel
from .choices import *


class SentDMProfile(BaseModel):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="sentdm_profile",
        blank=True,
        null=True,
    )
    organization = models.OneToOneField(
        "business.Organization",
        on_delete=models.CASCADE,
        related_name="sentdm_profile",
        blank=True,
        null=True,
    )
    profile_id = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=20, blank=True, default="")
    description = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=SentDMProfileStatus.choices,
        default=SentDMProfileStatus.INCOMPLETE,
        db_index=True,
    )
    phone_number = models.CharField(max_length=30, blank=True, default="", db_index=True)
    whatsapp_phone_number = models.CharField(max_length=30, blank=True, default="")
    billing_model = models.CharField(max_length=50, blank=True, default="organization")
    inherit_contacts = models.BooleanField(default=False)
    inherit_templates = models.BooleanField(default=False)
    inherit_tcr_brand = models.BooleanField(default=True)
    inherit_tcr_campaign = models.BooleanField(default=True)
    sandbox = models.BooleanField(default=True, db_index=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "sandbox"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.profile_id})"


class SentDMMessage(BaseModel):
    organization = models.ForeignKey(
        "business.Organization",
        on_delete=models.CASCADE,
        related_name="sentdm_messages",
        blank=True,
        null=True,
    )
    profile = models.ForeignKey(
        SentDMProfile,
        on_delete=models.SET_NULL,
        related_name="messages",
        blank=True,
        null=True,
    )
    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.SET_NULL,
        related_name="sentdm_messages",
        blank=True,
        null=True,
    )
    conversation = models.ForeignKey(
        "communications.Conversation",
        on_delete=models.SET_NULL,
        related_name="sentdm_messages",
        blank=True,
        null=True,
    )
    sent_message_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    direction = models.CharField(max_length=20, choices=SentDMMessageDirection.choices)
    channel = models.CharField(max_length=20, choices=SentDMChannel.choices, default=SentDMChannel.AUTO)
    from_number = models.CharField(max_length=30, blank=True, default="")
    to_number = models.CharField(max_length=30, blank=True, default="")
    body = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=SentDMMessageStatus.choices,
        default=SentDMMessageStatus.PENDING,
        db_index=True,
    )
    sandbox = models.BooleanField(default=True, db_index=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sent_message_id"]),
            models.Index(fields=["direction", "status"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return self.sent_message_id or f"{self.direction} {self.to_number}"



class SentDMCampaign(BaseModel):
    profile = models.ForeignKey(
        SentDMProfile,
        on_delete=models.CASCADE,
        related_name="campaigns",
    )
    organization = models.ForeignKey(
        "business.Organization",
        on_delete=models.CASCADE,
        related_name="sentdm_campaigns",
        blank=True,
        null=True,
    )
    campaign_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    campaign_type = models.CharField(max_length=50, blank=True, default="App")
    messaging_use_case_us = models.CharField(max_length=60, blank=True, default="CUSTOMER_CARE")
    volume = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=SentDMCampaignStatus.choices,
        default=SentDMCampaignStatus.SENT_CREATED,
        db_index=True,
    )
    submitted_to_tcr = models.BooleanField(default=False)
    tcr_campaign_id = models.CharField(max_length=120, blank=True, default="")
    sandbox = models.BooleanField(default=True, db_index=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["profile", "status"], name="sentdm_sent_profile_2eea8d_idx"),
            models.Index(fields=["organization", "status"], name="sentdm_sent_organiz_3f5744_idx"),
            models.Index(fields=["campaign_id"], name="sentdm_sent_campaig_a724fe_idx"),
        ]

    def __str__(self):
        return self.campaign_id or self.name

class SentDMWebhookEvent(BaseModel):
    event_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    event_type = models.CharField(max_length=120, blank=True, default="", db_index=True)
    profile_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    signature_verified = models.BooleanField(default=False)
    payload = models.JSONField(default=dict, blank=True)
    headers = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=SentDMWebhookEventStatus.choices,
        default=SentDMWebhookEventStatus.RECEIVED,
        db_index=True,
    )
    processed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "status"]),
            models.Index(fields=["event_id"]),
            models.Index(fields=["profile_id"]),
        ]

    def mark_processed(self):
        self.status = SentDMWebhookEventStatus.PROCESSED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at", "updated_at"])

