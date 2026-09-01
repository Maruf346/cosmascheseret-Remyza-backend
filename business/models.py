from django.core.exceptions import ValidationError
from django.db import models
from common.models import BaseModel
from accounts.models import User
from .choices import (
    OrganizationStatus, CountryCode, OnboardingStep, ProviderAccountStatus,
    Currency, DateFormat, Language, TimeFormat, AIReplyTone,PhoneProvider, PhoneNumberStatus, LocalVerificationStatus
)
from core.models import BusinessType, Industry
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone



class Organization(BaseModel):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="organization")
    name = models.CharField(max_length=255, db_index=True)
    logo = models.ImageField(upload_to="organizations/logo/", blank=True, null=True)
    country = models.CharField(max_length=2, choices=CountryCode.choices, default=CountryCode.US, db_index=True)

    business_type = models.ForeignKey(BusinessType, on_delete=models.PROTECT, related_name="organizations", blank=True, null=True)
    industry = models.ForeignKey(Industry, on_delete=models.PROTECT, related_name="organizations", blank=True, null=True)
    business_registration_identifier = models.CharField(max_length=255, blank=True, null=True)
    business_registration_number = models.CharField(max_length=255, blank=True, null=True)

    description = models.TextField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    business_hours = models.JSONField(default=dict, blank=True, help_text="Weekly business working hours.")
    sentdm_legal_name = models.CharField(max_length=255, blank=True, default="")
    sentdm_tax_id = models.CharField(max_length=50, blank=True, default="")
    sentdm_vertical = models.CharField(max_length=100, blank=True, default="PROFESSIONAL")
    sentdm_authorized_rep_name = models.CharField(max_length=255, blank=True, default="")
    sentdm_authorized_rep_title = models.CharField(max_length=100, blank=True, default="")
    sentdm_authorized_rep_email = models.EmailField(blank=True, default="")
    sentdm_authorized_rep_phone = models.CharField(max_length=30, blank=True, default="")
    sentdm_support_email = models.EmailField(blank=True, default="")
    sentdm_support_phone = models.CharField(max_length=30, blank=True, default="")
    sentdm_privacy_policy_url = models.URLField(blank=True, default="")
    sentdm_terms_url = models.URLField(blank=True, default="")
    sentdm_opt_in_url = models.URLField(blank=True, default="")
    sentdm_opt_in_description = models.TextField(blank=True, default="")
    sentdm_messaging_use_case = models.TextField(blank=True, default="")
    sentdm_messaging_use_case_us = models.CharField(max_length=60, blank=True, default="CUSTOMER_CARE")
    sentdm_sample_message_1 = models.TextField(blank=True, default="")
    sentdm_sample_message_2 = models.TextField(blank=True, default="")
    sentdm_sample_message_3 = models.TextField(blank=True, default="")
    sentdm_opt_in_confirmation_message = models.TextField(blank=True, default="")
    sentdm_opt_out_confirmation_message = models.TextField(blank=True, default="")
    sentdm_help_response_message = models.TextField(blank=True, default="")
    sentdm_expected_daily_volume = models.PositiveIntegerField(default=0)
    sentdm_whatsapp_waba_id = models.CharField(max_length=100, blank=True, default="")
    sentdm_whatsapp_phone_number_id = models.CharField(max_length=100, blank=True, default="")
    sentdm_whatsapp_access_token = models.TextField(blank=True, default="")
    
    is_verified = models.BooleanField(default=False, help_text="Organization verification status.")
    is_demo = models.BooleanField(default=False, help_text="Used for demo/testing organizations.")
    is_onboarding_completed = models.BooleanField(default=False)
    onboarding_step = models.CharField(max_length=50, choices=OnboardingStep.choices, default=OnboardingStep.ACCOUNT_CREATED)

    class Meta:
        db_table = "organizations"
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ["-created_at",]

        indexes = [
            models.Index(fields=["owner"], name="org_owner_idx"),
            models.Index(fields=["status"], name="org_status_idx"),
            models.Index(fields=["created_at"], name="org_created_idx"),
            models.Index(fields=["is_verified"], name="org_verified_idx"),
            models.Index(fields=["is_onboarding_completed"], name="org_onboarding_idx"),
        ]

        constraints = [
            models.UniqueConstraint(fields=["owner"], name="unique_organization_owner"),
        ]

    def __str__(self):
        return self.name
        
    @property
    def is_active(self):
        return (
            self.status == OrganizationStatus.ACTIVE
        )
    
    @property
    def has_phone_number(self):
        return self.phone_numbers.filter().exists()
    
    @property
    def primary_phone(self):
        return self.phone_numbers.filter(is_primary=True).first()

    @property
    def lead_count(self):
        return self.leads.count()
    
    def clean(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError(
                {
                    "name": "Organization name cannot be empty."
                }
            )

        if len(self.name) < 3:
            raise ValidationError(
                {
                    "name": "Organization name must contain at least 3 characters."
                }
            )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def complete_onboarding(self):
        self.is_onboarding_completed = True
        self.onboarding_step = OnboardingStep.COMPLETED
        self.save(update_fields=["is_onboarding_completed", "onboarding_step"])
        
    def activate(self):
        self.status = OrganizationStatus.ACTIVE
        self.save(update_fields=["status"])

    def suspend(self):
        self.status = OrganizationStatus.SUSPENDED
        self.save(update_fields=["status"])
    
    def deactivate(self):
        self.status = OrganizationStatus.INACTIVE
        self.save(update_fields=["status"])
    
    def update_logo(self, logo):
        self.logo = logo
        self.save(update_fields=["logo"])

    def update_favicon(self, favicon):
        self.favicon = favicon
        self.save(update_fields=["favicon"])
    
    def __repr__(self):
        return (
            f"<Organization("
            f"id={self.pk}, "
            f"name='{self.name}'"
            f")>"
        )

    def clean(self):
        super().clean()
        if self.website:
            self.website = self.website.strip()
        if self.email:
            self.email = self.email.lower().strip()

    @property
    def has_business_hours(self):
        return bool(self.business_hours)

class BusinessLink(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="links", blank=True, null=True)
    title = models.CharField(max_length=50)
    url = models.URLField(max_length=255)

class BusinessSetting(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="business_settings", blank=True, null=True)
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="settings", blank=True, null=True)
    language = models.CharField(max_length=10, choices=Language.choices, default=Language.ENGLISH)
    timezone = models.CharField(max_length=100, default="America/New_York")
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    date_format = models.CharField(max_length=20, choices=DateFormat.choices, default=DateFormat.MM_DD_YYYY)
    time_format = models.CharField(max_length=10, choices=TimeFormat.choices, default=TimeFormat.HOUR_12)
    lead_hot_score = models.PositiveSmallIntegerField(default=80, validators=[MinValueValidator(1), MaxValueValidator(100)], help_text="Minimum AI score to consider a lead as HOT.")
    
    reply_tone = models.CharField(max_length=50, choices=AIReplyTone.choices, default=AIReplyTone.FRIENDLY, help_text="Tone of AI-generated replies. (e.g., friendly, professional, casual)")
    auto_reply_enabled = models.BooleanField(default=True)
    reply_speed = models.PositiveBigIntegerField(default=0)
    auto_follow_up = models.BooleanField(default=True)
    
    push_notification_enabled = models.BooleanField(default=True)
    email_notification_enabled = models.BooleanField(default=True)
    notification_sound = models.BooleanField(default=True)

    class Meta:
        db_table = "business_settings"
        verbose_name = "Business Setting"
        verbose_name_plural = "Business Settings"
        ordering = ["organization__name"]
        indexes = [
            models.Index(fields=["language"], name="bs_language_idx"),
            models.Index(fields=["currency"], name="bs_currency_idx"),
            models.Index(fields=["auto_reply_enabled"], name="bs_auto_reply_idx"),
        ]

    def __str__(self):
        return f"{self.organization.name} Settings"

    def clean(self):
        super().clean()
        self.timezone = self.timezone.strip()

    @property
    def notifications_enabled(self):
        return self.push_notification_enabled or self.email_notification_enabled



class ProviderAccount(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="provider_account", blank=True, null=True)
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="provider_account")
    provider = models.CharField(max_length=20, choices=PhoneProvider.choices, default=PhoneProvider.TWILIO, db_index=True)
    account_sid = models.CharField(max_length=64, unique=True, db_index=True)
    owner_account_sid = models.CharField(max_length=64, blank=True, null=True)
    friendly_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=ProviderAccountStatus.choices, default=ProviderAccountStatus.ACTIVE)
    auth_token = models.CharField(max_length=255, blank=True, null=True)

    webhook_url = models.URLField(blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "provider_accounts"

        indexes = [
            models.Index(fields=["provider", "status"], name="provider_status_idx"),
        ]

    def __str__(self):
        return f"{self.organization.name} ({self.provider})"

class PhoneNumber(BaseModel):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="phone_numbers")
    provider = models.ForeignKey(ProviderAccount, on_delete=models.SET_NULL, blank=True, null=True, related_name="phone_numbers")

    phone_number = models.CharField(max_length=30, unique=True, db_index=True)
    provider_phone_sid = models.CharField(max_length=100, unique=True, db_index=True)
    capabilities = models.JSONField(default=dict, blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    country = models.CharField(max_length=2, db_index=True, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, default="")
    
    status = models.CharField(max_length=30, choices=PhoneNumberStatus.choices, default=PhoneNumberStatus.PENDING, db_index=True)
    is_primary = models.BooleanField(default=True)
    purchased_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "business_phone_numbers"
        verbose_name = "Phone Number"
        verbose_name_plural = "Phone Numbers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"], name="phone_org_status_idx"),
            models.Index(fields=["provider", "provider_phone_sid"], name="phone_provider_idx"),
            models.Index(fields=["country"], name="phone_country_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "is_primary"], condition=models.Q(is_primary=True), name="unique_primary_phone_per_org"
            ),
        ]

    def __str__(self):
        return self.phone_number

    @property
    def is_active(self):
        return self.status == PhoneNumberStatus.ACTIVE

    @property
    def sms_enabled(self):
        return self.capabilities.get("sms", False)

    @property
    def mms_enabled(self):
        return self.capabilities.get("mms", False)

    @property
    def local_verification(self):
        from twilio_app.models import LocalVerification
        verification, _ = LocalVerification.objects.get_or_create(
            phone_number=self,
            organization=self.organization
        )
        return verification

    @property
    def voice_enabled(self):
        return self.capabilities.get("voice", False)

class UserNotificationSettings(BaseModel):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="user_notification_setting", blank=True, null=True)
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="user_notification_setting", blank=True, null=True)
    
    all_notification = models.BooleanField(default=True)
    push_notification_enabled = models.BooleanField(default=True)
    email_alert_enabled = models.BooleanField(default=True)
    sms_alert_enabled = models.BooleanField(default=False)
    instant_lead_alert = models.BooleanField(default=True)
    weekly_performance_report = models.BooleanField(default=True)







# class TwilioUsage(models.Model):
#     organization = models.ForeignKey(Organization, ...)
#     phone_numbers = models.PositiveIntegerField(default=0)
#     sms_sent = models.PositiveIntegerField(default=0)
#     sms_received = models.PositiveIntegerField(default=0)
#     estimated_cost = models.DecimalField(...)
#     billing_month = models.DateField(...)

# class UsageLog(models.Model):
#     organization = models.ForeignKey(...)
#     event_type = models.CharField(...)
#     resource_sid = models.CharField(...)
#     quantity = models.IntegerField(...)
#     unit_cost = models.DecimalField(...)
#     total_cost = models.DecimalField(...)
#     created_at = models.DateTimeField(...)




