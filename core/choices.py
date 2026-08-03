from django.db import models


class NotificationType(models.TextChoices):
    HOT_LEAD = "hot_lead", "Hot Lead"
    AI_HANDOFF = "ai_handoff", "AI Handoff"
    MESSAGE_RECEIVED = "message_received", "Message Received"
    PAYMENT_SUCCESS = "payment_success", "Payment Success"
    PAYMENT_FAILED = "payment_failed", "Payment Failed"
    SUBSCRIPTION_EXPIRING = "subscription_expiring", "Subscription Expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired", "Subscription Expired"
    SYSTEM = "system", "System"


class NotificationPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class AuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    VIEW = "view", "View"

    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"

    SEND = "send", "Send"
    RECEIVE = "receive", "Receive"

    ENABLE = "enable", "Enable"
    DISABLE = "disable", "Disable"

    IMPORT = "import", "Import"
    EXPORT = "export", "Export"

    VERIFY = "verify", "Verify"

    ASSIGN = "assign", "Assign"
    UNASSIGN = "unassign", "Unassign"


class AuditModule(models.TextChoices):
    ACCOUNT = "account", "Account"
    BUSINESS = "business", "Business"
    CRM = "crm", "CRM"
    COMMUNICATION = "communication", "Communication"
    AI = "ai", "AI"
    KNOWLEDGE = "knowledge", "Knowledge"
    SUBSCRIPTION = "subscription", "Subscription"
    PAYMENT = "payment", "Payment"
    API = "api", "API"
    SYSTEM = "system", "System"


class APIKeyStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"


class SettingValueType(models.TextChoices):
    STRING = "string", "String"
    INTEGER = "integer", "Integer"
    BOOLEAN = "boolean", "Boolean"
    JSON = "json", "JSON"


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

class MessagingServiceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    DELETED = "deleted", "Deleted"

