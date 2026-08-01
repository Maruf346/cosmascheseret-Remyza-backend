from django.db import models
from .choices import (
    SettingValueType, NotificationType, NotificationPriority, FreeTrailNumberType,
    VerificationStatus, OptInType, BusinessTypeChoice, BusinessRegistrationAuthority
)
from common.models import BaseModel
from django.utils import timezone
from business.choices import PhoneNumberStatus

class Notification(BaseModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    body = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    priority = models.CharField(max_length=20, choices=NotificationPriority.choices, default=NotificationPriority.NORMAL)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.URLField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

class AuditLog(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="audit_logs")
    user = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=100)
    module = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.UUIDField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=10)
    request_path = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)

class SystemSetting(BaseModel):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField(default=dict, blank=True)
    value_type = models.CharField(max_length=255, choices=SettingValueType.choices)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)

class APIKey(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    api_key = models.CharField(max_length=128, unique=True, db_index=True)
    secret_key = models.CharField(max_length=255)
    permissions = models.JSONField(default=list, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class BusinessType(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Business Type"
        verbose_name_plural = "Business Types"

    def __str__(self):
        return self.name

class Industry(BaseModel):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name



class TwilioConfiguration(BaseModel):
    # Master Account
    master_account_sid = models.CharField(max_length=64, blank=True, null=True)
    master_account_auth_token = models.CharField(max_length=255, blank=True, null=True)

    # Trial Account / Shared Pool
    trial_account_name = models.CharField(max_length=255, blank=True, default="Trial Pool")
    trial_account_sid = models.CharField(max_length=64, blank=True, default="")
    trial_account_auth_token = models.CharField(max_length=255, blank=True, default="")

    

    # Default Configuration
    default_country = models.CharField(max_length=2, default="US")
    webhook_url = models.URLField(blank=True, default="")
    status_callback_url = models.URLField(blank=True, default="")
    fallback_webhook_url = models.URLField(blank=True, null=True)
    event_webhook_url = models.URLField(blank=True, null=True)
    auto_assign_webhook = models.BooleanField(default=True, null=True)
    voice_webhook_url = models.URLField(blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")

    # Trial Settings
    trial_duration_days = models.PositiveIntegerField(default=7)
    trial_sms_limit = models.PositiveIntegerField(default=50)
    trial_phone_limit = models.PositiveIntegerField(default=1)

    # Feature Flags
    enable_trial = models.BooleanField(default=True)
    auto_assign_webhook = models.BooleanField(default=True)
    auto_create_subaccount = models.BooleanField(default=True)
    auto_purchase_number = models.BooleanField(default=False)

    # Sync
    last_synced_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    

    def __str__(self):
        return "Twilio Configuration"

class FreeTrailPhoneNumber(BaseModel):
    owner_account_sid = models.CharField(max_length=64, blank=True, null=True)
    account_sid = models.CharField(max_length=64, db_index=True)
    account_auth_token = models.CharField(max_length=255, blank=True, null=True)
    
    number_type = models.CharField(max_length=20, choices=FreeTrailNumberType.choices, default=FreeTrailNumberType.TOLL_FREE)
    phone_number = models.CharField(max_length=30, unique=True, db_index=True)
    provider_phone_sid = models.CharField(max_length=100, unique=True, db_index=True)
    capabilities = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    webhook_url = models.URLField(blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")

    is_used = models.BooleanField(default=False)
    usages_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, choices=PhoneNumberStatus.choices, default=PhoneNumberStatus.PENDING, db_index=True)
    purchased_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

class UserFreeTrailNumber(BaseModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="trail_phone_numbers", blank=True, null=True)
    free_trail = models.ForeignKey(FreeTrailPhoneNumber, on_delete=models.SET_NULL, blank=True, null=True)
    trail_number = models.CharField(max_length=20, blank=True, null=True)
    start_at = models.DateTimeField(default=timezone.now)
    end_at = models.DateTimeField(blank=True, null=True)
    is_expired = models.BooleanField(default=False)
    is_released = models.BooleanField(default=False)

class TollFreeVerification(models.Model):
    # Relation
    phone_number = models.OneToOneField("business.PhoneNumber", on_delete=models.CASCADE, related_name="tfv_verification", blank=True, null=True)
    free_trail_phone_number = models.OneToOneField("FreeTrailPhoneNumber", on_delete=models.CASCADE, related_name="tfv_verification", blank=True, null=True)
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="tfv_verifications", blank=True, null=True)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="tfv_verifications", blank=True, null=True)

    # Twilio
    customer_profile_sid = models.CharField(max_length=64)
    tollfree_phone_number_sid = models.CharField(max_length=64)
    verification_sid = models.CharField(max_length=64, blank=True, help_text="Twilio TFV SID returned after submission.")
    external_reference_id = models.CharField(max_length=255, blank=True, null=True)

    # Business Information
    business_name = models.CharField(max_length=255)
    doing_business_as = models.CharField(max_length=255, blank=True)
    business_website = models.URLField()
    notification_email = models.EmailField()
    business_registration_number = models.CharField(max_length=100, blank=True)
    business_registration_authority = models.CharField(max_length=100, blank=True)
    business_registration_authority = models.CharField(max_length=30, choices=BusinessRegistrationAuthority.choices, blank=True,)
    business_registration_country = models.CharField(max_length=10, blank=True)
    business_registration_phone_number = models.CharField(max_length=30, blank=True)
    business_type = models.CharField(max_length=100, blank=True, choices=BusinessTypeChoice.choices)

    # Use Case
    use_case_categories = models.JSONField(default=list)
    use_case_summary = models.TextField()
    production_message_sample = models.TextField()
    message_volume = models.PositiveIntegerField(default=0)
    additional_information = models.TextField(blank=True)

    # Opt In
    opt_in_type = models.CharField(max_length=30, choices=OptInType.choices, default=OptInType.VERBAL)
    opt_in_image_urls = models.JSONField(default=list, blank=True)
    opt_in_confirmation_message = models.TextField(blank=True)
    opt_in_keywords = models.JSONField(default=list, blank=True)

    # Compliance
    help_message_sample = models.TextField(blank=True)
    privacy_policy_url = models.URLField(blank=True)
    terms_and_conditions_url = models.URLField(blank=True)
    age_gated_content = models.BooleanField(default=False)

    # Status
    verification_status = models.CharField(max_length=30, choices=VerificationStatus.choices, default=VerificationStatus.DRAFT)
    is_verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    rejected_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    rejection_reasons = models.TextField(blank=True)
    rejection_code = models.CharField(max_length=100, blank=True)

    # Store raw API data
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tfv_verifications"
        ordering = ["-created_at"]

    def __str__(self):
        if self.phone_number and self.phone_number.phone_number:
            return f"{self.phone_number.phone_number} - {self.verification_status}"
        elif self.free_trail_phone_number and self.free_trail_phone_number.phone_number:
            return f"{self.free_trail_phone_number.phone_number} - {self.verification_status}"
        else:
            return f"{self.business_name} - {self.verification_status}"

class TwilioWebhookLog(models.Model):
    method = models.CharField(max_length=10, blank=True, null=True)
    path = models.CharField(max_length=255, blank=True, null=True)

    headers = models.JSONField(default=dict)
    payload = models.JSONField(default=dict)
    body = models.TextField(blank=True)

    ip_address = models.GenericIPAddressField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)



