from django.db import models


# ==========================================================
# Organization
class OrganizationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"
    PENDING = "PENDING", "Pending Verification"
# ==========================================================


# ==========================================================
# Business
class BusinessType(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", "Individual"
    COMPANY = "COMPANY", "Company"
    AGENCY = "AGENCY", "Agency"
    STORE = "STORE", "Store"
    CLINIC = "CLINIC", "Clinic"
    RESTAURANT = "RESTAURANT", "Restaurant"
    EDUCATION = "EDUCATION", "Education"
    OTHER = "OTHER", "Other"

class Industry(models.TextChoices):
    AUTOMOTIVE = "AUTOMOTIVE", "Automotive"
    REAL_ESTATE = "REAL_ESTATE", "Real Estate"
    HEALTHCARE = "HEALTHCARE", "Healthcare"
    LEGAL = "LEGAL", "Legal"
    FINANCE = "FINANCE", "Finance"
    INSURANCE = "INSURANCE", "Insurance"
    HOME_SERVICE = "HOME_SERVICE", "Home Service"
    BEAUTY = "BEAUTY", "Beauty"
    EDUCATION = "EDUCATION", "Education"
    ECOMMERCE = "ECOMMERCE", "E-Commerce"
    RESTAURANT = "RESTAURANT", "Restaurant"
    TRAVEL = "TRAVEL", "Travel"
    SOFTWARE = "SOFTWARE", "Software"
    MARKETING = "MARKETING", "Marketing"
    CONSULTING = "CONSULTING", "Consulting"
    OTHER = "OTHER", "Other"
# ==========================================================


# ==========================================================
# Phone Number
class PhoneProvider(models.TextChoices):
    TWILIO = "TWILIO", "Twilio"

class PhoneNumberStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    PENDING = "PENDING", "Pending"
    VERIFICATION_PENDING = "VERIFICATION PENDING", "Verification Pending"
    VERIFICATION_REJECTED = "VERIFICATION REJECTED", "Verification Rejected"
    RELEASED = "RELEASED", "Released"
    FAILED = "FAILED", "Failed"
# ==========================================================


# ==========================================================
# Country
class CountryCode(models.TextChoices):
    US = "US", "United States"
    CA = "CA", "Canada"
    GB = "GB", "United Kingdom"
    AU = "AU", "Australia"
    BD = "BD", "Bangladesh"

# ==========================================================


# ==========================================================
# Currency
class Currency(models.TextChoices):
    USD = "USD", "US Dollar"
    CAD = "CAD", "Canadian Dollar"
    GBP = "GBP", "British Pound"
    AUD = "AUD", "Australian Dollar"
    BDT = "BDT", "Bangladeshi Taka"

# ==========================================================


# ==========================================================
# Time Format
class TimeFormat(models.TextChoices):
    HOUR_12 = "12H", "12 Hours"
    HOUR_24 = "24H", "24 Hours"
# ==========================================================


# ==========================================================
# Date Format
class DateFormat(models.TextChoices):
    MM_DD_YYYY = "MM/DD/YYYY", "MM/DD/YYYY"
    DD_MM_YYYY = "DD/MM/YYYY", "DD/MM/YYYY"
    YYYY_MM_DD = "YYYY-MM-DD", "YYYY-MM-DD"
# ==========================================================


# ==========================================================
# Language
class Language(models.TextChoices):
    ENGLISH = "EN", "English"
    SPANISH = "ES", "Spanish"
    FRENCH = "FR", "French"
    GERMAN = "DE", "German"
# ==========================================================

class OnboardingStep(models.TextChoices):
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    PROFILE_COMPLETED = "PROFILE_COMPLETED"
    NUMBER_ASSIGNED = "NUMBER_ASSIGNED"
    AI_CONFIGURED = "AI_CONFIGURED"
    COMPLETED = "COMPLETED"



class ProviderAccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DISABLED = "disabled", "Disabled"
    PENDING = "pending", "Pending"
    FAILED = "failed", "Failed"


class AIReplyTone(models.TextChoices):
    PROFESSIONAL = "professional", "Professional"
    FRIENDLY = "friendly", "Friendly"
    CASUAL = "casual", "Casual"


