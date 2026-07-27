from django.db import models
from common.models import BaseModel
from business.models import Organization
from communications.models import Message
from .choices import AIProvider, PromptType, AIRequestStatus

class AIConfiguration(BaseModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="ai_configuration")
    
    provider = models.CharField(max_length=30, choices=AIProvider.choices, default=AIProvider.OPENAI)
    model_name = models.CharField(max_length=100, default="gpt-4.1-mini")
    system_prompt = models.TextField(blank=True)
    temperature = models.DecimalField(max_digits=3, decimal_places=2, default=0.30)
    max_tokens = models.PositiveIntegerField(default=1000)
    top_p = models.DecimalField(max_digits=3, decimal_places=2, default=1.00)
    
    auto_reply_enabled = models.BooleanField(default=True)
    confidence_threshold = models.DecimalField(max_digits=4, decimal_places=2, default=0.80)
    handoff_score = models.PositiveSmallIntegerField(default=80)
    is_active = models.BooleanField(default=True)

class PromptTemplate(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="prompt_templates")
    name = models.CharField(max_length=100)
    prompt_type = models.CharField(max_length=50, choices=PromptType.choices)
    content = models.TextField()
    variables = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "ai_prompt_templates"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_prompt_version"
            ),
        ]

class AIUsageLog(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="ai_usage_logs")
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.CharField(max_length=30)
    model_name = models.CharField(max_length=100)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    processing_time = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=AIRequestStatus.choices)
    metadata = models.JSONField(default=dict, blank=True)

class AIModelLog(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="ai_logs")
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.CharField(max_length=30)
    model_name = models.CharField(max_length=100)
    request_payload = models.JSONField()
    response_payload = models.JSONField(null=True, blank=True)
    response_text = models.TextField(blank=True)
    latency = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=AIRequestStatus.choices)
    error_message = models.TextField(blank=True)

