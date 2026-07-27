from django.db import models
from common.models import BaseModel
from .choices import (
    PlanType, SubscriptionStatus, BillingCycle, BillingType,
    PaymentProvider, PaymentStatus, PurchasePlatform, InvoiceStatus, Currency
)
import uuid

class SubscriptionPlan(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    plan_type = models.CharField(max_length=20, choices=PlanType.choices)
    billing_type = models.CharField(max_length=20, choices=BillingType.choices)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    trial_days = models.PositiveSmallIntegerField(default=0)
    
    sms_limit = models.PositiveIntegerField(default=0)
    lead_limit = models.PositiveIntegerField(default=0)
    ai_reply_limit = models.PositiveIntegerField(default=0)
    
    custom_welcome_message = models.BooleanField(default=False)
    ai_auto_reply = models.BooleanField(default=True)
    lead_scoring = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    bulk_import = models.BooleanField(default=False)
    
    ai_token_limit = models.PositiveIntegerField(default=0)
    phone_number_limit = models.PositiveSmallIntegerField(default=1)
    knowledge_document_limit = models.PositiveSmallIntegerField(default=0)
    storage_limit = models.PositiveIntegerField(default=0, help_text="Storage limit in MB.")
    is_active = models.BooleanField(default=True)

class UserSubscription(BaseModel):
    uuid = models.UUIDField(max_length=120, db_index=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="subscriptions", blank=True, null=True)
    organization = models.ForeignKey("business.Organization", on_delete=models.CASCADE, related_name="subscription", blank=True, null=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=SubscriptionStatus.choices, default=SubscriptionStatus.AWAITING_PAYMENT, db_index=True)
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, blank=True, null=True)
    start_date = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

class Payment(BaseModel):
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name="payments")
    transaction_id = models.CharField(max_length=150, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

class Invoice(BaseModel):
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name="invoices")
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING, db_index=True)
    pdf_file = models.FileField(upload_to="invoices/", null=True, blank=True)

class PurchaseInfo(BaseModel):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="purchase_info")
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_info")
    
    platform = models.CharField(max_length=20, choices=PurchasePlatform.choices)
    product_id = models.CharField(max_length=100, blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    # transaction_id = models.CharField(max_length=255, unique=True, db_index=True)
    original_transaction_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    purchase_token = models.TextField(blank=True, default="")
    receipt_data = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

