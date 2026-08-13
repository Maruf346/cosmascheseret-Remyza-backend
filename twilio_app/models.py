from django.db import models
from .choices import (
    CustomerProfileStatus, A2PProfileStatus, TrustHubEvaluationStatus, A2PBrandStatus, A2PBrandType, A2PCampaignStatus, MessagingServiceStatus, LocalVerificationStatus, VerificationStep, VerificationStepStatus,

    BusinessRegistrationAuthority, BusinessTypeChoice, OptInType, VerificationStatus
)
from django.utils import timezone

# ===============================================================================================================
# =====================================Local Verification Step by Step Model=====================================
class CustomerProfile(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="new_customer_profile")
    profile_sid = models.CharField(max_length=64, unique=True, db_index=True)
    policy_sid = models.CharField(max_length=64, blank=True, default="")
    friendly_name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    status = models.CharField(max_length=50, choices=CustomerProfileStatus.choices, default=CustomerProfileStatus.DRAFT)
    failure_reason = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} - {self.profile_sid}"

class BusinessEndUser(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="business_end_users")
    customer_profile = models.OneToOneField(CustomerProfile, on_delete=models.CASCADE, related_name="new_end_users", null=True, blank=True)
    end_user_sid = models.CharField(max_length=64, unique=True, db_index=True)
    friendly_name = models.CharField(max_length=255, blank=True, default="")
    end_user_type = models.CharField(max_length=100, default="customer_profile_business_end_user")
    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=100, blank=True, default="")
    business_industry = models.CharField(max_length=255, blank=True, default="")
    business_registration_identifier = models.CharField(max_length=255, blank=True, default="")
    business_registration_number = models.CharField(max_length=255, blank=True, default="")
    website_url = models.URLField(blank=True, default="")
    status = models.CharField(max_length=50, blank=True, default="")
    failure_reason = models.TextField(blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business_name} - {self.end_user_sid}"

class BusinessAddress(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="business_addresses")
    twilio_sid = models.CharField(max_length=64, unique=True, db_index=True)
    account_sid = models.CharField(max_length=255, blank=True, null=True)
    friendly_name = models.CharField(max_length=255, blank=True, null=True, default="")
    customer_name = models.CharField(max_length=255, blank=True, null=True, default="")
    street = models.CharField(max_length=255)
    street_secondary = models.CharField(max_length=255, blank=True, null=True, default="")
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=30)
    country = models.CharField(max_length=10)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    twilio_data = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def full_address(self):
        parts = [self.address_line_1, self.address_line_2, self.city, self.state, self.postal_code, self.country]
        return ", ".join(part for part in parts if part)

    def __str__(self):
        return f"{self.organization} - {self.street}, {self.city}"

class TrustHubEntityAssignment(models.Model):
    customer_profile = models.OneToOneField(CustomerProfile, on_delete=models.CASCADE, related_name="new_entity_assignments", null=True, blank=True)
    a2p_profile = models.ForeignKey("A2PProfile", on_delete=models.CASCADE, related_name="new_entity_assignments", null=True, blank=True)
    object_sid = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=100, blank=True, default="")
    assignment_sid = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=50, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

class A2PProfile(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="new_a2p_profile")
    profile_sid = models.CharField(max_length=64, unique=True, db_index=True)
    policy_sid = models.CharField(max_length=64, blank=True,null=True, default="")
    friendly_name = models.CharField(max_length=255, blank=True, null=True, default="")
    email = models.EmailField(blank=True, null=True, default="")
    # status = models.CharField(max_length=50, choices=A2PProfileStatus.choices, default=A2PProfileStatus.DRAFT)
    status = models.CharField(max_length=50, blank=True, null=True, default="")
    failure_reason = models.TextField(blank=True, null=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} - {self.profile_sid}"

class TrustHubEvaluation(models.Model):
    customer_profile = models.OneToOneField(CustomerProfile, on_delete=models.CASCADE, related_name="new_evaluations", null=True, blank=True)
    a2p_profile = models.OneToOneField(A2PProfile, on_delete=models.CASCADE, related_name="new_evaluations", null=True, blank=True)
    evaluation_sid = models.CharField(max_length=64, blank=True, default="", db_index=True)
    policy_sid = models.CharField(max_length=64, blank=True, default="")
    # status = models.CharField(max_length=50, choices=TrustHubEvaluationStatus.choices, default=TrustHubEvaluationStatus.PENDING)
    status = models.CharField(max_length=50, blank=True, null=True, default="")
    failure_reason = models.TextField(blank=True, default="")
    evaluated_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

class A2PBrand(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="new_a2p_brands")
    customer_profile = models.OneToOneField(CustomerProfile, on_delete=models.PROTECT, related_name="new_brands")
    a2p_profile = models.OneToOneField(A2PProfile, on_delete=models.PROTECT, related_name="new_brands")
    brand_sid = models.CharField(max_length=64, unique=True, db_index=True)
    brand_type = models.CharField(max_length=50, choices=A2PBrandType.choices, default=A2PBrandType.STANDARD, null=True, blank=True)
    # status = models.CharField(max_length=50, choices=A2PBrandStatus.choices, default=A2PBrandStatus.DRAFT)
    status = models.CharField(max_length=50, blank=True, null=True, default="")
    identity_status = models.CharField(max_length=100, blank=True, null=True, default="")
    tcr_id = models.CharField(max_length=255, blank=True, null=True)
    brand_score = models.CharField(max_length=255, blank=True, null=True)
    brand_feedback = models.CharField(max_length=255, blank=True, null=True)
    russell_3000 = models.CharField(max_length=255, blank=True, null=True)
    government_entity = models.CharField(max_length=255, blank=True, null=True)
    tax_exempt_status = models.CharField(max_length=255, blank=True, null=True)
    mock = models.CharField(max_length=255, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} - {self.brand_sid}"

class A2PCampaign(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="new_a2p_campaigns")
    brand = models.OneToOneField(A2PBrand, on_delete=models.PROTECT, related_name="new_campaigns")
    campaign_sid = models.CharField(max_length=64, unique=True, db_index=True)
    campaign_type = models.CharField(max_length=100, blank=True, default="")
    use_case = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    message_flow = models.TextField(blank=True, default="")
    message_samples = models.JSONField(default=list, blank=True)
    opt_in_keywords = models.JSONField(default=list, blank=True)
    opt_out_keywords = models.JSONField(default=list, blank=True)
    help_keywords = models.JSONField(default=list, blank=True)
    opt_in_message = models.TextField(blank=True, default="")
    opt_out_message = models.TextField(blank=True, default="")
    help_message = models.TextField(blank=True, default="")
    status = models.CharField(max_length=50, choices=A2PCampaignStatus.choices, default=A2PCampaignStatus.DRAFT)
    failure_reason = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} - {self.campaign_sid}"

class MessagingService(models.Model):
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="new_messaging_service")
    service_sid = models.CharField(max_length=64, unique=True, db_index=True)
    friendly_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=MessagingServiceStatus.choices, default=MessagingServiceStatus.ACTIVE)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.service_sid


# ===============================================================================================================
# ===============================================================================================================


# ===============================================================================================================
# =====================================Local Verification Model==================================================
class LocalVerification(models.Model):
    phone_number = models.OneToOneField("business.PhoneNumber", on_delete=models.CASCADE, related_name="new_local_verification")
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="new_local_verifications")
    status = models.CharField(max_length=50, choices=LocalVerificationStatus.choices, default=LocalVerificationStatus.NOT_STARTED, blank=True, null=True)

    messaging_service = models.ForeignKey(MessagingService, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_verifications")
    messaging_service_attachment_sid = models.CharField(max_length=64, blank=True, default="")

    a2p_brand = models.ForeignKey(A2PBrand, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_verifications")
    a2p_campaign = models.ForeignKey(A2PCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_verifications")
    complete_progress = models.PositiveSmallIntegerField(default=0)
    current_step = models.CharField(max_length=100, blank=True, default="")
    failure_reason = models.TextField(blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    customer_profile_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    end_user_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    authorized_representative_1_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    authorized_representative_2_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    address_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    supporting_document_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    end_user_assign_to_customer_profiles_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    authorized_representative_1_assign_to_customer_profiles_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    authorized_representative_2_assign_to_customer_profiles_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    primary_customer_profile_assign_to_customer_profile_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    supporting_document_assign_to_customer_profile_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    phone_number_assign_to_customer_profile_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    profile_evaluation_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    
    a2p_profile_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    a2p_end_user_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    end_user_assign_to_a2p_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    customer_profile_assign_to_a2p_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    a2p_evaluation_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    a2p_brand_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    messaging_service_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    messaging_service_assign_sid = models.CharField(max_length=64, blank=True, null=True, default="")
    a2p_campaign_sid = models.CharField(max_length=64, blank=True, null=True, default="")


    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} - {self.phone_number}"

    def save(self, *args, **kwargs):
        progress = 0
        if self.messaging_service:
            progress += 33
        if self.a2p_brand:
            progress += 33
        if self.a2p_campaign:
            progress += 34

        self.complete_progress = progress
        # self.status = (
        #     self.a2p_brand
        #     and self.a2p_campaign
        #     and self.messaging_service
        #     and self.a2p_brand.status == "APPROVED"
        #     and self.a2p_campaign.status == "APPROVED"
        # )
        super().save(*args, **kwargs)

class LocalVerificationStep(models.Model):
    verification = models.ForeignKey(LocalVerification, on_delete=models.CASCADE, related_name="new_steps")
    step = models.CharField(max_length=100, choices=VerificationStep.choices)
    status = models.CharField(max_length=50, choices=VerificationStepStatus.choices, default=VerificationStepStatus.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    response_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "twilio_local_verification_steps"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["verification", "step"],
                name="unique_verification_step",
            ),
        ]

# ===============================================================================================================
# ===============================================================================================================

# ===============================================================================================================
# =====================================Toll Free Verification Model==============================================
class TollFreeVerification(models.Model):
    # Relation
    phone_number = models.OneToOneField("business.PhoneNumber", on_delete=models.CASCADE, related_name="new_tfv_verification", blank=True, null=True)
    free_trail_phone_number = models.OneToOneField("core.FreeTrailPhoneNumber", on_delete=models.CASCADE, related_name="new_tfv_verification", blank=True, null=True)
    organization = models.OneToOneField("business.Organization", on_delete=models.CASCADE, related_name="new_tfv_verifications", blank=True, null=True)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="new_tfv_verifications", blank=True, null=True)

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
        ordering = ["-created_at"]

    def __str__(self):
        if self.phone_number and self.phone_number.phone_number:
            return f"{self.phone_number.phone_number} - {self.verification_status}"
        elif self.free_trail_phone_number and self.free_trail_phone_number.phone_number:
            return f"{self.free_trail_phone_number.phone_number} - {self.verification_status}"
        else:
            return f"{self.business_name} - {self.verification_status}"

# ===============================================================================================================
# ===============================================================================================================


class TwilioRequestLog(models.Model):
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="new_twilio_request_logs")
    verification = models.ForeignKey(LocalVerification, on_delete=models.SET_NULL, null=True, blank=True, related_name="new_twilio_requests")
    operation = models.CharField(max_length=150)
    method = models.CharField(max_length=10, default="POST")
    endpoint = models.TextField(blank=True, default="")
    twilio_sid = models.CharField(max_length=64, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "twilio_request_logs"
        ordering = ["-created_at"]

class TwilioWebhookLog(models.Model):
    method = models.CharField(max_length=10, blank=True, null=True)
    path = models.CharField(max_length=255, blank=True, null=True)

    headers = models.JSONField(default=dict)
    payload = models.JSONField(default=dict)
    body = models.TextField(blank=True)

    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

