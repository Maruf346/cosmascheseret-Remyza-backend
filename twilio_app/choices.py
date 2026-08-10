from django.db import models

class CustomerProfileStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"
    IN_REVIEW = "IN_REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    SUSPENDED = "SUSPENDED", "Suspended"

class A2PProfileStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING = "PENDING", "Pending"
    IN_REVIEW = "IN_REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"

class TrustHubEvaluationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_REVIEW = "IN_REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    FAILED = "FAILED", "Failed"

class A2PBrandStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING = "PENDING", "Pending"
    IN_REVIEW = "IN_REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    FAILED = "FAILED", "Failed"


class A2PBrandType(models.TextChoices):
    STANDARD = "STANDARD", "Standard"
    LOW_VOLUME_STANDARD = "LOW_VOLUME_STANDARD", "Low Volume Standard"
    SOLE_PROPRIETOR = "SOLE_PROPRIETOR", "Sole Proprietor"

class A2PCampaignStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING = "PENDING", "Pending"
    IN_REVIEW = "IN_REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    SUSPENDED = "SUSPENDED", "Suspended"

class MessagingServiceStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"
    DELETED = "deleted", "Deleted"

class LocalVerificationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    BRAND_PENDING = "BRAND_PENDING", "Brand Pending"
    CAMPAIGN_PENDING = "CAMPAIGN_PENDING", "Campaign Pending"
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    FAILED = "FAILED", "Failed"
    COMPLETED = "COMPLETED", "Completed"

class VerificationStep(models.TextChoices):
    MESSAGING_SERVICE = "MESSAGING_SERVICE", "Messaging Service"
    PHONE_ATTACHMENT = "PHONE_ATTACHMENT", "Phone Attachment"
    CUSTOMER_PROFILE = "CUSTOMER_PROFILE", "Customer Profile"
    BUSINESS_END_USER = "BUSINESS_END_USER", "Business End User"
    BUSINESS_ADDRESS = "BUSINESS_ADDRESS", "Business Address"
    CUSTOMER_ASSIGNMENT = "CUSTOMER_ASSIGNMENT", "Customer Assignment"
    A2P_PROFILE = "A2P_PROFILE", "A2P Profile"
    A2P_ASSIGNMENT = "A2P_ASSIGNMENT", "A2P Assignment"
    A2P_EVALUATION = "A2P_EVALUATION", "A2P Evaluation"
    BRAND = "BRAND", "Brand"
    CAMPAIGN = "CAMPAIGN", "Campaign"
    CAMPAIGN_ASSIGNMENT = "CAMPAIGN_ASSIGNMENT", "Campaign Assignment"
    MESSAGING_ASSIGNMENT = "MESSAGING_ASSIGNMENT", "Messaging Assignment"


class VerificationStepStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    SKIPPED = "SKIPPED", "Skipped"



class FreeTrailNumberType(models.TextChoices):
    LOCAL = "LOCAL"
    TOLL_FREE = "TOLL_FREE"

class VerificationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    PENDING = "pending", "Pending Review"
    IN_REVIEW = "in_review", "In Review"
    TWILIO_APPROVED = "twilio_approved", "Twilio Approved"
    REJECTED = "rejected", "Rejected"
    REJECTED_PERMANENT = "rejected_permanent", "Rejected Permanent"
    CANCELED = "canceled", "Canceled"

class OptInType(models.TextChoices):
    VERBAL = "VERBAL", "Verbal"
    WEB_FORM = "WEB_FORM", "Web Form"
    PAPER_FORM = "PAPER_FORM", "Paper Form"
    MOBILE_QR_CODE = "MOBILE_QR_CODE", "Mobile QR Code"
    TEXT = "TEXT", "Text"
    IVR = "IVR", "IVR"
    UNKNOWN = "UNKNOWN", "Unknown"



class BusinessTypeChoice(models.TextChoices):
    PRIVATE_PROFIT = "PRIVATE_PROFIT", "Private Profit"
    PUBLIC_PROFIT = "PUBLIC_PROFIT", "Public Profit"
    SOLE_PROPRIETOR = "SOLE_PROPRIETOR", "Sole Proprietor"
    NON_PROFIT = "NON_PROFIT", "Non-Profit"
    GOVERNMENT = "GOVERNMENT", "Government"

class UseCaseCategory(models.TextChoices):
    TWO_FACTOR_AUTHENTICATION = "TWO_FACTOR_AUTHENTICATION", "Two-Factor Authentication"
    ACCOUNT_NOTIFICATIONS = "ACCOUNT_NOTIFICATIONS", "Account Notifications"
    CUSTOMER_CARE = "CUSTOMER_CARE", "Customer Care"
    CHARITY_NONPROFIT = "CHARITY_NONPROFIT", "Charity / Nonprofit"
    DELIVERY_NOTIFICATIONS = "DELIVERY_NOTIFICATIONS", "Delivery Notifications"
    FRAUD_ALERT_MESSAGING = "FRAUD_ALERT_MESSAGING", "Fraud Alert Messaging"
    EVENTS = "EVENTS", "Events"
    HIGHER_EDUCATION = "HIGHER_EDUCATION", "Higher Education"
    K12 = "K12", "K-12 Education"
    MARKETING = "MARKETING", "Marketing"
    POLLING_AND_VOTING_NON_POLITICAL = "POLLING_AND_VOTING_NON_POLITICAL", "Polling & Voting (Non-Political)"
    POLITICAL_ELECTION_CAMPAIGNS = "POLITICAL_ELECTION_CAMPAIGNS", "Political Election Campaigns"
    PUBLIC_SERVICE_ANNOUNCEMENT = "PUBLIC_SERVICE_ANNOUNCEMENT", "Public Service Announcement"
    SECURITY_ALERT = "SECURITY_ALERT", "Security Alert"


class BusinessRegistrationAuthority(models.TextChoices):
    EIN = "EIN", "Employer Identification Number (EIN)"
    CBN = "CBN", "Company Business Number (CBN)"
    CRN = "CRN", "Company Registration Number (CRN)"
    PROVINCIAL_NUMBER = "PROVINCIAL_NUMBER", "Provincial Registration Number"
    VAT = "VAT", "VAT Number"
    ACN = "ACN", "Australian Company Number (ACN)"
    ABN = "ABN", "Australian Business Number (ABN)"
    BRN = "BRN", "Business Registration Number (BRN)"
    SIREN = "SIREN", "French SIREN"
    SIRET = "SIRET", "French SIRET"
    NZBN = "NZBN", "New Zealand Business Number (NZBN)"
    UST_IDNR = "USt-IdNr", "German VAT ID (USt-IdNr)"
    CIF = "CIF", "Spanish CIF"
    NIF = "NIF", "Spanish NIF"
    CNPJ = "CNPJ", "Brazilian CNPJ"
    UID = "UID", "UID"
    NEQ = "NEQ", "Quebec Enterprise Number (NEQ)"
    OTHER = "OTHER", "Other"


