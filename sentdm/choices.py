from django.db import models


class SentDMProfileStatus(models.TextChoices):
    INCOMPLETE = "incomplete", "Incomplete"
    PROCESSING = "processing", "Processing"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    FAILED = "failed", "Failed"


class SentDMMessageDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class SentDMMessageStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"


class SentDMChannel(models.TextChoices):
    AUTO = "auto", "Auto"
    SMS = "sms", "SMS"
    RCS = "rcs", "RCS"
    WHATSAPP = "whatsapp", "WhatsApp"


class SentDMWebhookEventStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class SentDMCampaignStatus(models.TextChoices):
    SENT_CREATED = "SENT_CREATED", "Sent Created"
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
    FAILED = "FAILED", "Failed"