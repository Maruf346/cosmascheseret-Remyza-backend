from django.db import models
from common.models import BaseModel
from .choices import LeadStage, LeadActivityType

class Lead(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="leads")
    business_phone = models.ForeignKey("business.PhoneNumber", on_delete=models.PROTECT, related_name="leads")
    
    full_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=30, db_index=True)
    company = models.CharField(max_length=255, blank=True)
    stage = models.CharField(max_length=20, choices=LeadStage.choices, default=LeadStage.NEW, db_index=True)
    score = models.PositiveSmallIntegerField(default=0)
    ai_enabled = models.BooleanField(default=True)
    
    # assigned_to = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_leads")
    handed_over_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_incoming_at = models.DateTimeField(null=True, blank=True)
    last_outgoing_at = models.DateTimeField(null=True, blank=True)
    last_ai_reply_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crm_leads"
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["organization", "contact_number"]),
            models.Index(fields=["stage"]),
            models.Index(fields=["score"]),
            models.Index(fields=["last_message_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "contact_number"], condition=models.Q(is_deleted=False), name="unique_lead_per_organization"
            ),
        ]

class LeadActivity(BaseModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=50, choices=LeadActivityType.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "crm_lead_activities"
        ordering = ["-created_at",]
        indexes = [
            models.Index(fields=["lead"]),
            models.Index(fields=["activity_type"]),
        ]

class LeadTag(BaseModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "crm_lead_tags"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["lead", "name"], condition=models.Q(is_deleted=False), name="unique_lead_tag"),
        ]

class LeadTagAssignment(BaseModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tag_assignments")
    tag = models.ForeignKey(LeadTag, on_delete=models.CASCADE, related_name="lead_assignments")
    assigned_by_ai = models.BooleanField(default=False)

    class Meta:
        db_table = "crm_lead_tag_assignments"
        constraints = [
            models.UniqueConstraint(fields=["lead", "tag"], condition=models.Q(is_deleted=False), name="unique_tag_assignment"),
        ]
        indexes = [
            models.Index(fields=["lead"]),
            models.Index(fields=["tag"]),
        ]

    def __str__(self):
        return f"{self.lead.contact_number} → {self.tag.name}"

class FollowUpReminder(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="reminders")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="reminders")
    scheduled_time = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)
    is_sent = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "crm_followup_reminders"
        ordering = ["scheduled_time"]

    def __str__(self):
        return f"Reminder for {self.lead.contact_number} at {self.scheduled_time}"
