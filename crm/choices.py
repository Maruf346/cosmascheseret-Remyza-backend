from django.db import models


class LeadStage(models.TextChoices):
    COLD = "cold", "Cold"
    WARM = "warm", "Warm"
    HOT = "hot", "Hot"
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    QUALIFIED = "qualified", "Qualified"
    CONVERTED = "converted", "Converted"
    LOST = "lost", "Lost"


class LeadSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    CSV_UPLOAD = "csv_upload", "CSV Upload"
    AUTO_CAPTURE = "auto_capture", "Auto Capture"
    SENTDM = "sentdm", "Sent.dm"


class LeadActivityType(models.TextChoices):
    CREATED = "created", "Created"
    MESSAGE_RECEIVED = "message_received", "Message Received"
    MESSAGE_SENT = "message_sent", "Message Sent"
    AI_REPLIED = "ai_replied", "AI Replied"
    STAGE_CHANGED = "stage_changed", "Stage Changed"
    TAG_ADDED = "tag_added", "Tag Added"
    TAG_REMOVED = "tag_removed", "Tag Removed"
    HANDOFF = "handoff", "Handoff"
    NOTE_ADDED = "note_added", "Note Added"