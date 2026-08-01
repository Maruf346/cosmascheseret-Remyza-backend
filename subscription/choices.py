from django.db import models

class PlanType(models.TextChoices):
    FREE_TRAIL = "free_trial", "Free Trail"
    PAID = "paid", "Paid"
    # STARTER = "starter", "Starter"
    # GROWTH = "growth", "Growth"
    # BUSINESS = "business", "Business"
    # ENTERPRISE = "enterprise", "Enterprise"

class BillingType(models.TextChoices):
    DAY = "day", "Day"
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"
    LIFETIME = "lifetime", "Lifetime"

class SubscriptionStatus(models.TextChoices):
    TRIAL = "trial", "Trial"
    AWAITING_PAYMENT = "awaiting_payment", "Awaiting Payment"
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past Due"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"
    SUSPENDED = "suspended", "Suspended"
    CLOSE = "close", "Close"

class PaymentProvider(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    GOOGLE_PLAY = "google_play", "Google Play"
    APP_STORE = "app_store", "App Store"
    MANUAL = "manual", "Manual"

class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"
    PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"

class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"
    CANCELLED = "cancelled", "Cancelled"
    VOID = "void", "Void"

class PurchasePlatform(models.TextChoices):
    GOOGLE_PLAY = "google_play", "Google Play"
    APP_STORE = "app_store", "App Store"

class BillingCycle(models.TextChoices):
    DAY = "day", "Day"
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"
    LIFETIME = "lifetime", "Lifetime"

class Currency(models.TextChoices):
    USD = "USD", "US Dollar"
    EUR = "EUR", "Euro"
    GBP = "GBP", "British Pound"
    CAD = "CAD", "Canadian Dollar"
    AUD = "AUD", "Australian Dollar"

