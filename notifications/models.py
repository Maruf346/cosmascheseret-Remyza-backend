import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationType(models.TextChoices):
    WELCOME = "welcome", "Welcome"
    NEW_USER = "new_user", "New User"
    SUBSCRIPTION_CREATED = "subscription_created", "Subscription Created"
    SUBSCRIPTION_ACTIVE = "subscription_active", "Subscription Active"
    SENTDM_PROFILE_REQUESTED = "sentdm_profile_requested", "Sent.dm Profile Requested"
    SENTDM_PROFILE_COMPLETED = "sentdm_profile_completed", "Sent.dm Profile Completed"
    SENTDM_CAMPAIGN_REQUESTED = "sentdm_campaign_requested", "Sent.dm Campaign Requested"
    WHATSAPP_CONNECTION_REQUESTED = "whatsapp_connection_requested", "WhatsApp Connection Requested"
    NEW_LEAD = "new_lead", "New Lead"
    MESSAGE_RECEIVED = "message_received", "Message Received"
    SYSTEM_ALERT = "system_alert", "System Alert"


class NotificationPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_notifications",
    )
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        identifier = getattr(self.user, "email", "") or getattr(self.user, "phone_number", "") or str(self.user_id)
        return f"{self.title} - {identifier}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])