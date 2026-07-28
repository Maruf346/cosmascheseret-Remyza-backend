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


from django.db import models


class BusinessType(models.TextChoices):
    SOLE_PROPRIETOR = "SOLE_PROPRIETOR", "Sole Proprietor"
    PARTNERSHIP = "PARTNERSHIP", "Partnership"
    COOPERATIVE = "COOPERATIVE", "Cooperative"
    NON_PROFIT = "NON_PROFIT", "Non-Profit"
    PRIVATE_PROFIT = "PRIVATE_PROFIT", "Private Profit"
    PUBLIC_PROFIT = "PUBLIC_PROFIT", "Public Profit"
    GOVERNMENT = "GOVERNMENT", "Government"

