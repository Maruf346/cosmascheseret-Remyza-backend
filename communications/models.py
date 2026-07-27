from django.db import models
from common.models import BaseModel
from .choices import (
    ConversationStatus, MessageDirection, MessageStatus, MessageType, SentimentType, IntentType, HandoffReason, ProviderType, QueueStatus, MessageTemplateType
)

class Conversation(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="conversations")
    lead = models.ForeignKey("crm.Lead", on_delete=models.CASCADE, related_name="conversations")
    status = models.CharField(max_length=20, choices=ConversationStatus.choices, default=ConversationStatus.ACTIVE, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    total_messages = models.PositiveIntegerField(default=0)
    unread_messages = models.PositiveIntegerField(default=0)
    ai_enabled = models.BooleanField(default=True)
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crm_conversations"
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["organization", "status"], name="conv_org_status_idx"),
            models.Index(fields=["lead", "status"], name="conv_lead_status_idx"),
            models.Index(fields=["last_message_at"], name="conv_last_message_idx"),
        ]

    def __str__(self):
        return f"Conversation #{self.pk} - {self.lead.contact_number}"

    @property
    def is_active(self):
        return self.status == ConversationStatus.ACTIVE

class Message(BaseModel):
    lead = models.ForeignKey("crm.Lead", on_delete=models.CASCADE, related_name="messages")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=10, choices=MessageDirection.choices, db_index=True)
    sender = models.CharField(max_length=20)
    recipient = models.CharField(max_length=20)
    
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    content = models.TextField()
    
    provider_message_sid = models.CharField(max_length=100, unique=True, db_index=True)
    provider_status = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=MessageStatus.choices, default=MessageStatus.PENDING, db_index=True)
    
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    is_ai_generated = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crm_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="msg_conv_created_idx"),
            models.Index(fields=["lead", "created_at"], name="msg_lead_created_idx"),
            models.Index(fields=["provider_message_sid"], name="msg_provider_sid_idx"),
            models.Index(fields=["status"], name="msg_status_idx"),
            models.Index(fields=["direction"], name="msg_direction_idx"),
        ]

class MessageAttachment(BaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="messages/")
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.PositiveBigIntegerField()
    provider_media_sid = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "communication_message_attachments"

class AIAnalysis(BaseModel):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="ai_analysis")
    sentiment = models.CharField(max_length=20, choices=SentimentType.choices, blank=True)
    intent = models.CharField(max_length=50, choices=IntentType.choices, blank=True)
    lead_score = models.PositiveSmallIntegerField(default=0)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    summary = models.TextField(blank=True)
    suggested_reply = models.TextField(blank=True)
    entities = models.JSONField(default=dict, blank=True)
    extracted_data = models.JSONField(default=dict, blank=True)
    ai_model = models.CharField(max_length=100, blank=True)
    processing_time_ms = models.PositiveIntegerField(default=0)
    analyzed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = "ai_message_analysis"
        ordering = ["-analyzed_at",]
        indexes = [
            models.Index(fields=["lead_score"]),
            models.Index(fields=["sentiment"]),
            models.Index(fields=["intent"]),
            models.Index(fields=["analyzed_at"]),
        ]

    def __str__(self):
        return f"AI Analysis - {self.message.provider_message_sid}"

class HandoffEvent(BaseModel):
    lead = models.ForeignKey("crm.Lead", on_delete=models.CASCADE, related_name="handoff_events")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="handoff_events")
    reason = models.CharField(max_length=100, choices=HandoffReason.choices)
    ai_score = models.PositiveSmallIntegerField(default=0)
    ai_summary = models.TextField(blank=True)
    handed_off_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_handoff_events"
        ordering = ["-handed_off_at",]

class WebhookEvent(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="webhook_events")
    provider = models.CharField(max_length=20, choices=ProviderType.choices)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "communication_webhook_events"
        indexes = [
            models.Index(fields=["processed"]),
            models.Index(fields=["event_type"]),
        ]

class OutboundMessageQueue(BaseModel):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="queue")
    priority = models.PositiveSmallIntegerField(default=5)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retry = models.PositiveSmallIntegerField(default=3)
    scheduled_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=QueueStatus.choices, default=QueueStatus.PENDING)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "communication_outbound_queue"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["scheduled_at"]),
        ]


class StaticMessageTemplate(BaseModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="message_templates")
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="message_templates")
    template_type = models.CharField(max_length=40, choices=MessageTemplateType.choices, db_index=True)
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user", "template_type"],
                name="unique_static_template",
            )
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.template_type}"
