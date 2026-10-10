import base64
import binascii
import hashlib
import hmac
import json
import time
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ai.ai_service import AIService
from business.models import PhoneNumber, PhoneNumberStatus
from communications.choices import ConversationStatus, MessageDirection, MessageStatus
from communications.choices import MessageTemplateType
from communications.models import Conversation, Message, StaticMessageTemplate
from crm.choices import AutomatedFollowUpStatus, LeadActivityType, LeadSource, LeadStage
from crm.models import AutomatedFollowUp, Contact, FollowUpReminder, Lead, LeadActivity

from .choices import SentDMChannel, SentDMCampaignStatus, SentDMMessageDirection, SentDMMessageStatus, SentDMProfileStatus, SentDMWebhookEventStatus, SentDMWhatsAppConnectionSource, SentDMWhatsAppConnectionStatus
from .client import SentDMClient, SentDMClientError
from .models import SentDMCampaign, SentDMMessage, SentDMProfile, SentDMWebhookEvent


OPT_OUT_KEYWORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
HELP_KEYWORDS = {"HELP"}


def normalize_profile_status(value):
    status_value = (value or SentDMProfileStatus.INCOMPLETE).lower()
    if status_value == "completed":
        return SentDMProfileStatus.APPROVED
    if status_value in SentDMProfileStatus.values:
        return status_value
    return SentDMProfileStatus.INCOMPLETE


def build_short_name(value, fallback="CHESERA"):
    cleaned = "".join(char for char in (value or "") if char.isalnum())
    short_name = cleaned[:11].upper()
    if len(short_name) >= 3 and any(char.isalpha() for char in short_name):
        return short_name
    return fallback[:11].upper()



SENTDM_WHATSAPP_FIELDS = (
    "sentdm_whatsapp_waba_id",
    "sentdm_whatsapp_phone_number_id",
    "sentdm_whatsapp_access_token",
)


def get_sentdm_whatsapp_business_account(organization):
    values = {
        field: str(getattr(organization, field, "") or "").strip()
        for field in SENTDM_WHATSAPP_FIELDS
    }
    if not all(values.values()):
        return None
    return {
        "waba_id": values["sentdm_whatsapp_waba_id"],
        "phone_number_id": values["sentdm_whatsapp_phone_number_id"],
        "access_token": values["sentdm_whatsapp_access_token"],
    }


def clean_attr(obj, field, default=""):
    return str(getattr(obj, field, default) or "").strip()


def build_sentdm_message_flow(organization):
    brand_name = clean_attr(organization, "sentdm_legal_name") or clean_attr(organization, "name")
    method = clean_attr(organization, "sentdm_opt_in_method").lower()
    starting_url = clean_attr(organization, "sentdm_opt_in_starting_url")
    opt_in_url = clean_attr(organization, "sentdm_opt_in_form_url") or clean_attr(organization, "sentdm_opt_in_url")
    screenshot_url = clean_attr(organization, "sentdm_opt_in_screenshot_url")
    checkbox_text = clean_attr(organization, "sentdm_opt_in_checkbox_text")
    disclaimer = clean_attr(organization, "sentdm_sms_disclaimer_text")
    legacy_description = clean_attr(organization, "sentdm_opt_in_description")

    method_labels = {
        "web": "web/digital form",
        "spoken": "spoken consent",
        "physical": "physical/paper form",
        "subscriber_initiated": "subscriber-initiated first message",
    }
    method_label = method_labels.get(method, method or "documented opt-in process")

    parts = [f"SMS opt-in for {brand_name} is collected through {method_label}."]
    if method == "web":
        parts.append(f"Subscribers navigate to {opt_in_url} from {starting_url}.")
        parts.append("The opt-in form includes an optional, unchecked SMS consent checkbox.")
    elif method == "spoken":
        parts.append("Consent is collected verbally using the documented script below before any SMS is sent.")
    elif method == "physical":
        parts.append("Consent is collected on a physical form before any SMS is sent.")
    elif method == "subscriber_initiated":
        parts.append("The business publishes its Chesera/Sent.dm number with SMS disclosures, and subscribers opt in by sending the first message.")

    if legacy_description:
        parts.append(legacy_description)
    if checkbox_text:
        parts.append(f"Checkbox/consent text: {checkbox_text}")
    if disclaimer:
        parts.append(f"SMS disclaimer: {disclaimer}")
    if screenshot_url:
        parts.append(f"Hosted opt-in screenshot: {screenshot_url}")
    parts.append(f"Privacy Policy: {clean_attr(organization, 'sentdm_privacy_policy_url')}")
    parts.append(f"Terms: {clean_attr(organization, 'sentdm_terms_url')}")
    parts.append("Privacy policy confirms no mobile information will be sold or shared with third parties for promotional or marketing purposes.")
    return " ".join(part for part in parts if part).strip()


def build_sentdm_brand_compliance(organization, user):
    legal_name = clean_attr(organization, "sentdm_legal_name") or clean_attr(organization, "name")
    return {
        "inherit": False,
        "legal_name": legal_name,
        "business_name": clean_attr(organization, "name") or legal_name,
        "tax_id": clean_attr(organization, "sentdm_tax_id"),
        "tax_id_type": clean_attr(organization, "sentdm_tax_id_type") or "EIN",
        "ein_issuing_country": clean_attr(organization, "sentdm_ein_issuing_country") or "US",
        "entity_type": clean_attr(organization, "sentdm_entity_type"),
        "street": clean_attr(organization, "sentdm_brand_street"),
        "city": clean_attr(organization, "sentdm_brand_city"),
        "state": clean_attr(organization, "sentdm_brand_state"),
        "postal_code": clean_attr(organization, "sentdm_brand_postal_code"),
        "country": clean_attr(organization, "country") or "US",
        "website": clean_attr(organization, "website"),
        "contact_name": clean_attr(organization, "sentdm_authorized_rep_name") or getattr(user, "full_name", ""),
        "contact_email": clean_attr(organization, "sentdm_authorized_rep_email") or clean_attr(organization, "sentdm_support_email") or getattr(user, "email", ""),
        "contact_phone": clean_attr(organization, "sentdm_authorized_rep_phone") or getattr(user, "phone_number", ""),
    }


def build_sentdm_campaign_compliance(organization):
    volume = int(getattr(organization, "sentdm_expected_daily_volume", 0) or 0)
    campaign = {
        "inherit": False,
        "description": clean_attr(organization, "sentdm_messaging_use_case"),
        "message_flow": build_sentdm_message_flow(organization),
        "use_cases": [clean_attr(organization, "sentdm_messaging_use_case_us").upper() or "CUSTOMER_CARE"],
        "opt_in_message": clean_attr(organization, "sentdm_opt_in_confirmation_message"),
        "opt_out_message": clean_attr(organization, "sentdm_opt_out_confirmation_message"),
        "help_message": clean_attr(organization, "sentdm_help_response_message"),
        "opt_in_keywords": "YES, START, SUBSCRIBE",
        "opt_out_keywords": "STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT",
        "help_keywords": "HELP",
        "privacy_policy_link": clean_attr(organization, "sentdm_privacy_policy_url"),
        "terms_and_conditions_link": clean_attr(organization, "sentdm_terms_url"),
        "volume": str(volume) if volume > 0 else "",
    }
    return campaign


def build_sentdm_profile_compliance(organization, user):
    return {
        "brand": build_sentdm_brand_compliance(organization, user),
        "campaign": build_sentdm_campaign_compliance(organization),
    }


def build_profile_payload(organization, user, overrides=None):
    overrides = overrides or {}
    name = getattr(organization, "name", "") or user.full_name or user.phone_number
    email = getattr(organization, "email", "") or user.email or ""
    support_email = getattr(organization, "sentdm_support_email", "") or email

    payload = {
        "name": overrides.get("name") or name,
        "short_name": overrides.get("short_name") or build_short_name(name, fallback=f"USR{user.id}"),
        "description": overrides.get("description") or f"Chesera messaging profile for {name}",
        "email": overrides.get("email") or support_email,
        "inherit_contacts": False,
        "inherit_templates": False,
        "billing_model": "organization",
    }

    if organization:
        payload["smsCountry"] = "US"
        payload["smsNumberType"] = "TEN_DLC"
        payload["compliance"] = build_sentdm_profile_compliance(organization, user)

    whatsapp_business_account = get_sentdm_whatsapp_business_account(organization)
    if whatsapp_business_account:
        payload["whatsapp_business_account"] = whatsapp_business_account
    return payload

def get_response_whatsapp_phone_number(data):
    return (
        data.get("whatsapp_phone_number")
        or data.get("whatsappPhoneNumber")
        or data.get("sending_whatsapp_number")
        or data.get("sendingWhatsappNumber")
        or ""
    )


def is_agent_whatsapp_active(profile):
    return bool(profile and getattr(profile, "is_agent_whatsapp_active", False))


def upsert_profile_from_response(response, *, user=None, organization=None, direct_whatsapp_requested=False):
    data = response.get("data") or {}
    profile_id = data.get("id")
    if not profile_id:
        return None

    existing_profile = SentDMProfile.objects.filter(profile_id=profile_id).first()
    returned_whatsapp_number = get_response_whatsapp_phone_number(data)
    now = timezone.now()

    if direct_whatsapp_requested:
        whatsapp_source = SentDMWhatsAppConnectionSource.DIRECT
        whatsapp_status = SentDMWhatsAppConnectionStatus.ACTIVE if returned_whatsapp_number else SentDMWhatsAppConnectionStatus.PENDING
        whatsapp_phone_number = returned_whatsapp_number
        whatsapp_connected_at = now if returned_whatsapp_number else None
    elif existing_profile and existing_profile.whatsapp_connection_source == SentDMWhatsAppConnectionSource.DIRECT:
        whatsapp_source = SentDMWhatsAppConnectionSource.DIRECT
        whatsapp_status = existing_profile.whatsapp_connection_status
        whatsapp_phone_number = returned_whatsapp_number or existing_profile.whatsapp_phone_number
        whatsapp_connected_at = existing_profile.whatsapp_connected_at
    elif returned_whatsapp_number:
        whatsapp_source = SentDMWhatsAppConnectionSource.INHERITED
        whatsapp_status = SentDMWhatsAppConnectionStatus.NOT_CONNECTED
        whatsapp_phone_number = ""
        whatsapp_connected_at = None
    else:
        whatsapp_source = SentDMWhatsAppConnectionSource.NONE
        whatsapp_status = SentDMWhatsAppConnectionStatus.NOT_CONNECTED
        whatsapp_phone_number = ""
        whatsapp_connected_at = None

    profile, _ = SentDMProfile.objects.update_or_create(
        profile_id=profile_id,
        defaults={
            "user": user,
            "organization": organization,
            "name": data.get("name") or "",
            "short_name": data.get("short_name") or "",
            "description": data.get("description") or "",
            "email": data.get("email") or "",
            "status": normalize_profile_status(data.get("status")),
            "phone_number": data.get("sending_phone_number") or "",
            "whatsapp_phone_number": whatsapp_phone_number,
            "whatsapp_connection_source": whatsapp_source,
            "whatsapp_connection_status": whatsapp_status,
            "whatsapp_connection_error": "",
            "whatsapp_connected_at": whatsapp_connected_at,
            "whatsapp_last_synced_at": now if whatsapp_source != SentDMWhatsAppConnectionSource.NONE else None,
            "billing_model": data.get("billing_model") or "organization",
            "inherit_contacts": bool(data.get("inherit_contacts", False)),
            "inherit_templates": bool(data.get("inherit_templates", False)),
            "inherit_tcr_brand": bool(data.get("inherit_tcr_brand", True)),
            "inherit_tcr_campaign": bool(data.get("inherit_tcr_campaign", True)),
            "sandbox": getattr(settings, "SENTDM_SANDBOX_MODE", True),
            "last_synced_at": now,
            "raw_response": response,
        },
    )
    return profile


def create_profile_for_user(user, profile_data=None):
    organization = getattr(user, "organization", None)
    payload = build_profile_payload(organization, user, overrides=profile_data)
    client = SentDMClient()
    response = client.create_profile(payload, idempotency_key=f"chesera-profile-user-{user.id}")
    profile = upsert_profile_from_response(response, user=user, organization=organization, direct_whatsapp_requested=bool(get_sentdm_whatsapp_business_account(organization)))
    return profile, response



def build_direct_whatsapp_payload(waba_id, phone_number_id, access_token):
    return {
        "whatsapp_business_account": {
            "waba_id": str(waba_id or "").strip(),
            "phone_number_id": str(phone_number_id or "").strip(),
            "access_token": str(access_token or "").strip(),
        }
    }


def save_organization_whatsapp_credentials(organization, whatsapp_data):
    if not organization:
        return
    organization.sentdm_whatsapp_waba_id = whatsapp_data["waba_id"]
    organization.sentdm_whatsapp_phone_number_id = whatsapp_data["phone_number_id"]
    organization.sentdm_whatsapp_access_token = whatsapp_data["access_token"]
    organization.save(
        update_fields=[
            "sentdm_whatsapp_waba_id",
            "sentdm_whatsapp_phone_number_id",
            "sentdm_whatsapp_access_token",
            "updated_at",
        ]
    )


def mark_profile_whatsapp_failed(profile, error):
    if not profile:
        return
    now = timezone.now()
    profile.whatsapp_connection_source = SentDMWhatsAppConnectionSource.DIRECT
    profile.whatsapp_connection_status = SentDMWhatsAppConnectionStatus.FAILED
    profile.whatsapp_connection_error = str(error)
    profile.whatsapp_last_synced_at = now
    profile.save(
        update_fields=[
            "whatsapp_connection_source",
            "whatsapp_connection_status",
            "whatsapp_connection_error",
            "whatsapp_last_synced_at",
            "updated_at",
        ]
    )


def connect_agent_whatsapp_for_user(user, whatsapp_data, profile_id=None):
    profile = get_profile_for_user(user, profile_id=profile_id)
    if not profile:
        raise ValidationError({"profile": "Create a Sent.dm Sender Profile before connecting WhatsApp."})

    account = build_direct_whatsapp_payload(
        whatsapp_data.get("waba_id"),
        whatsapp_data.get("phone_number_id"),
        whatsapp_data.get("access_token"),
    )["whatsapp_business_account"]
    if not all(account.values()):
        raise ValidationError(
            {
                "whatsapp": "waba_id, phone_number_id, and access_token are all required to connect the agent's WhatsApp Business Account."
            }
        )

    payload = {"whatsapp_business_account": account}
    client = SentDMClient()
    try:
        response = client.update_profile(
            profile.profile_id,
            payload,
            idempotency_key=f"chesera-profile-whatsapp-{profile.profile_id}-{int(time.time())}",
        )
    except SentDMClientError as exc:
        mark_profile_whatsapp_failed(profile, exc)
        raise

    save_organization_whatsapp_credentials(profile.organization, account)
    profile = upsert_profile_from_response(
        response,
        user=profile.user or user,
        organization=profile.organization or get_organization_for_user(user),
        direct_whatsapp_requested=True,
    )
    return profile, response
SENTDM_10DLC_REQUIRED_FIELDS = {
    "sentdm_legal_name": "Legal business name is required for 10DLC registration.",
    "sentdm_tax_id": "Business tax ID/EIN is required for 10DLC brand registration.",
    "sentdm_tax_id_type": "Tax ID type is required for 10DLC brand registration.",
    "sentdm_entity_type": "Business entity type is required for 10DLC brand registration.",
    "sentdm_brand_street": "Business street address is required for 10DLC brand registration.",
    "sentdm_brand_city": "Business city is required for 10DLC brand registration.",
    "sentdm_brand_state": "Business state is required for 10DLC brand registration.",
    "sentdm_brand_postal_code": "Business postal code is required for 10DLC brand registration.",
    "sentdm_authorized_rep_name": "Authorized representative name is required for 10DLC brand registration.",
    "sentdm_authorized_rep_email": "Authorized representative email is required for 10DLC brand registration.",
    "sentdm_authorized_rep_phone": "Authorized representative phone is required for 10DLC brand registration.",
    "sentdm_support_email": "Support email is required for HELP autoresponses.",
    "sentdm_privacy_policy_url": "Privacy Policy URL is required for 10DLC registration.",
    "sentdm_terms_url": "Terms and Conditions URL is required for 10DLC registration.",
    "sentdm_opt_in_method": "Opt-in method is required: web, spoken, physical, or subscriber_initiated.",
    "sentdm_sms_disclaimer_text": "SMS disclaimer text is required for 10DLC opt-in documentation.",
    "sentdm_messaging_use_case": "Campaign description/use case is required for 10DLC registration.",
    "sentdm_messaging_use_case_us": "US messaging use-case value is required for 10DLC registration.",
    "sentdm_sample_message_1": "At least one realistic sample message is required for 10DLC registration.",
    "sentdm_opt_in_confirmation_message": "Opt-in confirmation autoresponse is required for 10DLC registration.",
    "sentdm_opt_out_confirmation_message": "Opt-out confirmation autoresponse is required for 10DLC registration.",
    "sentdm_help_response_message": "HELP autoresponse is required for 10DLC registration.",
}
SENTDM_SAMPLE_FIELDS = ("sentdm_sample_message_1", "sentdm_sample_message_2", "sentdm_sample_message_3")
SENTDM_TWO_SAMPLE_USE_CASES = {"MARKETING", "MIXED", "LOW_VOLUME"}
SENTDM_OPT_IN_METHODS = {"web", "spoken", "physical", "subscriber_initiated"}


def add_missing_field(missing_fields, messages, field, message):
    if field not in missing_fields:
        missing_fields.append(field)
        messages[field] = message


def validate_sentdm_structured_opt_in(organization, missing_fields, messages):
    method = clean_attr(organization, "sentdm_opt_in_method").lower()
    if method and method not in SENTDM_OPT_IN_METHODS:
        add_missing_field(
            missing_fields,
            messages,
            "sentdm_opt_in_method",
            "Opt-in method must be one of: web, spoken, physical, subscriber_initiated.",
        )
        return

    if not getattr(organization, "sentdm_privacy_policy_no_mobile_sharing", False):
        add_missing_field(
            missing_fields,
            messages,
            "sentdm_privacy_policy_no_mobile_sharing",
            "Confirm that the privacy policy says mobile information will not be sold or shared with third parties for promotional or marketing purposes.",
        )

    if method in {"web", "physical"}:
        if not getattr(organization, "sentdm_sms_consent_optional", False):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_sms_consent_optional",
                "SMS consent must be optional and distinct from general form submission.",
            )
        if not getattr(organization, "sentdm_sms_checkbox_not_prefilled", False):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_sms_checkbox_not_prefilled",
                "The SMS consent checkbox must not be prefilled.",
            )

    if method == "web":
        if not clean_attr(organization, "sentdm_opt_in_starting_url"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_starting_url",
                "Starting URL is required to document how subscribers navigate to the opt-in form.",
            )
        if not clean_attr(organization, "sentdm_opt_in_form_url") and not clean_attr(organization, "sentdm_opt_in_url"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_form_url",
                "Public opt-in form URL is required for web opt-in documentation.",
            )
        if not clean_attr(organization, "sentdm_opt_in_checkbox_text"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_checkbox_text",
                "SMS checkbox/consent text is required for web opt-in documentation.",
            )
    elif method == "spoken":
        if not clean_attr(organization, "sentdm_opt_in_description"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_description",
                "Spoken opt-in requires a script explaining how verbal SMS consent is collected.",
            )
    elif method == "physical":
        if not clean_attr(organization, "sentdm_opt_in_description"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_description",
                "Physical opt-in requires a description of where/how the paper form is collected.",
            )
        if not clean_attr(organization, "sentdm_opt_in_screenshot_url"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_screenshot_url",
                "Hosted screenshot URL is required for physical opt-in form documentation.",
            )
    elif method == "subscriber_initiated":
        if not clean_attr(organization, "sentdm_opt_in_description"):
            add_missing_field(
                missing_fields,
                messages,
                "sentdm_opt_in_description",
                "Subscriber-initiated opt-in requires a description of where the number/keyword and disclosures are published.",
            )

    use_case = clean_attr(organization, "sentdm_messaging_use_case_us").upper()
    if use_case == "MARKETING" and not getattr(organization, "sentdm_marketing_messages_disclosed", False):
        add_missing_field(
            missing_fields,
            messages,
            "sentdm_marketing_messages_disclosed",
            "Marketing campaigns must explicitly disclose that subscribers are accepting marketing texts.",
        )
    if use_case in {"POLITICAL", "CHARITY"} and not getattr(organization, "sentdm_donation_solicitation_disclosed", False):
        add_missing_field(
            missing_fields,
            messages,
            "sentdm_donation_solicitation_disclosed",
            "Political or charity campaigns must disclose whether donations will be solicited.",
        )


def get_organization_for_user(user):
    organization = getattr(user, "organization", None)
    if not organization:
        return None
    return organization


def get_profile_for_user(user, profile_id=None):
    if profile_id:
        return SentDMProfile.objects.filter(profile_id=profile_id).first()

    profile = SentDMProfile.objects.filter(user=user).first()
    if profile:
        return profile

    organization = get_organization_for_user(user)
    if organization:
        return SentDMProfile.objects.filter(organization=organization).first()
    return None


def get_sentdm_compliance_readiness(user, profile_id=None):
    organization = get_organization_for_user(user)
    missing_fields = []

    if not organization:
        return {
            "ready": False,
            "missing_fields": ["organization"],
            "messages": {"organization": "Business profile is required before messaging activation."},
            "profile_id": "",
            "sample_message_count": 0,
        }

    messages = {}
    for field, message in SENTDM_10DLC_REQUIRED_FIELDS.items():
        if not str(getattr(organization, field, "") or "").strip():
            missing_fields.append(field)
            messages[field] = message
    validate_sentdm_structured_opt_in(organization, missing_fields, messages)

    use_case = str(getattr(organization, "sentdm_messaging_use_case_us", "") or "").upper()
    sample_messages = get_sentdm_sample_messages(organization)
    if use_case in SENTDM_TWO_SAMPLE_USE_CASES and len(sample_messages) < 2:
        missing_fields.append("sentdm_sample_message_2")
        messages["sentdm_sample_message_2"] = "Marketing, mixed, and low-volume campaigns require at least two realistic sample messages."

    profile = get_profile_for_user(user, profile_id=profile_id)
    if not profile:
        missing_fields.append("sentdm_profile")
        messages["sentdm_profile"] = "Create a Sent.dm Sender Profile before submitting a 10DLC campaign."

    return {
        "ready": not missing_fields,
        "missing_fields": missing_fields,
        "messages": messages,
        "profile_id": profile.profile_id if profile else "",
        "sample_message_count": len(sample_messages),
        "messaging_use_case_us": use_case,
    }




def get_sentdm_profile_creation_readiness(user):
    organization = get_organization_for_user(user)
    missing_fields = []

    if not organization:
        return {
            "ready": False,
            "missing_fields": ["organization"],
            "messages": {"organization": "Business profile is required before creating a Sent.dm Sender Profile."},
            "sample_message_count": 0,
            "messaging_use_case_us": "",
        }

    messages = {}
    for field, message in SENTDM_10DLC_REQUIRED_FIELDS.items():
        if field == "sentdm_profile":
            continue
        if not str(getattr(organization, field, "") or "").strip():
            missing_fields.append(field)
            messages[field] = message
    validate_sentdm_structured_opt_in(organization, missing_fields, messages)

    use_case = str(getattr(organization, "sentdm_messaging_use_case_us", "") or "").upper()
    sample_messages = get_sentdm_sample_messages(organization)
    if use_case in SENTDM_TWO_SAMPLE_USE_CASES and len(sample_messages) < 2:
        missing_fields.append("sentdm_sample_message_2")
        messages["sentdm_sample_message_2"] = "Marketing, mixed, and low-volume campaigns require at least two realistic sample messages."

    whatsapp_values = {
        field: str(getattr(organization, field, "") or "").strip()
        for field in SENTDM_WHATSAPP_FIELDS
    }
    provided_whatsapp_fields = [field for field, value in whatsapp_values.items() if value]
    if 0 < len(provided_whatsapp_fields) < len(SENTDM_WHATSAPP_FIELDS):
        for field, value in whatsapp_values.items():
            if not value and field not in missing_fields:
                missing_fields.append(field)
                messages[field] = "To connect WhatsApp, waba_id, phone_number_id, and access_token are all required. Leave all three blank to skip WhatsApp."

    return {
        "ready": not missing_fields,
        "missing_fields": missing_fields,
        "messages": messages,
        "warnings": [
            "No direct WhatsApp WABA credentials were provided. Sent.dm documents that Sender Profile creation must inherit an organization-level WhatsApp Business Account or include direct WABA credentials; if the organization channel is not configured, Sent.dm may reject profile creation with HTTP 422."
        ] if not get_sentdm_whatsapp_business_account(organization) else [],
        "has_direct_whatsapp_business_account": bool(get_sentdm_whatsapp_business_account(organization)),
        "sample_message_count": len(sample_messages),
        "messaging_use_case_us": use_case,
    }


def get_sentdm_sample_messages(organization):
    return [
        str(getattr(organization, field, "") or "").strip()
        for field in SENTDM_SAMPLE_FIELDS
        if str(getattr(organization, field, "") or "").strip()
    ]


def build_10dlc_campaign_payload(organization, *, campaign_name=None, campaign_type="App"):
    use_case = str(getattr(organization, "sentdm_messaging_use_case_us", "") or "CUSTOMER_CARE").upper()
    volume = int(getattr(organization, "sentdm_expected_daily_volume", 0) or 0)

    campaign = {
        "name": campaign_name or f"{organization.name} Customer Messaging",
        "description": clean_attr(organization, "sentdm_messaging_use_case"),
        "type": campaign_type or "App",
        "useCases": [
            {
                "messagingUseCaseUs": use_case,
                "sampleMessages": get_sentdm_sample_messages(organization),
            }
        ],
        "messageFlow": build_sentdm_message_flow(organization),
        "privacyPolicyLink": clean_attr(organization, "sentdm_privacy_policy_url"),
        "termsAndConditionsLink": clean_attr(organization, "sentdm_terms_url"),
        "optinMessage": clean_attr(organization, "sentdm_opt_in_confirmation_message"),
        "optoutMessage": clean_attr(organization, "sentdm_opt_out_confirmation_message"),
        "helpMessage": clean_attr(organization, "sentdm_help_response_message"),
        "optinKeywords": "YES, START, SUBSCRIBE",
        "optoutKeywords": "STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT",
        "helpKeywords": "HELP",
    }
    if volume > 0:
        campaign["volume"] = str(volume)

    return {"campaign": campaign}


def normalize_campaign_status(value):
    status_value = value or SentDMCampaignStatus.SENT_CREATED
    if status_value in SentDMCampaignStatus.values:
        return status_value
    return SentDMCampaignStatus.SENT_CREATED


def upsert_campaign_from_response(response, *, profile, payload):
    data = response.get("data") or {}
    campaign = payload.get("campaign") or {}
    campaign_id = data.get("id") or ""

    defaults = {
        "profile": profile,
        "organization": profile.organization,
        "campaign_id": campaign_id,
        "name": data.get("name") or campaign.get("name") or "",
        "description": data.get("description") or campaign.get("description") or "",
        "campaign_type": data.get("type") or campaign.get("type") or "App",
        "messaging_use_case_us": ((campaign.get("useCases") or [{}])[0]).get("messagingUseCaseUs", "CUSTOMER_CARE"),
        "volume": data.get("volume") or campaign.get("volume") or "",
        "status": normalize_campaign_status(data.get("status")),
        "submitted_to_tcr": bool(data.get("submittedToTCR", False)),
        "tcr_campaign_id": data.get("tcrCampaignId") or "",
        "sandbox": getattr(settings, "SENTDM_SANDBOX_MODE", True),
        "last_synced_at": timezone.now(),
        "raw_response": response,
    }

    if campaign_id:
        campaign_obj, _ = SentDMCampaign.objects.update_or_create(campaign_id=campaign_id, defaults=defaults)
    else:
        campaign_obj = SentDMCampaign.objects.create(**defaults)
    return campaign_obj


def create_10dlc_campaign_for_user(user, *, profile_id=None, campaign_name=None, campaign_type="App"):
    readiness = get_sentdm_compliance_readiness(user, profile_id=profile_id)
    if not readiness["ready"]:
        return None, None, readiness

    profile = get_profile_for_user(user, profile_id=profile_id)
    organization = profile.organization or get_organization_for_user(user)
    payload = build_10dlc_campaign_payload(organization, campaign_name=campaign_name, campaign_type=campaign_type)
    client = SentDMClient()

    if profile.inherit_tcr_campaign:
        client.update_profile(
            profile.profile_id,
            {"inherit_tcr_campaign": False},
            idempotency_key=f"chesera-profile-campaign-mode-{profile.profile_id}",
        )
        profile.inherit_tcr_campaign = False
        profile.save(update_fields=["inherit_tcr_campaign", "updated_at"])

    response = client.create_campaign(
        profile.profile_id,
        payload,
        idempotency_key=f"chesera-10dlc-campaign-{profile.profile_id}",
    )
    campaign = upsert_campaign_from_response(response, profile=profile, payload=payload)
    return campaign, response, readiness
def complete_profile(profile, request):
    webhook_url = request.build_absolute_uri(reverse("sentdm-profile-ready-webhook"))
    client = SentDMClient()
    response = client.complete_profile(profile.profile_id, webhook_url)
    profile.raw_response = response
    profile.last_synced_at = timezone.now()
    profile.save(update_fields=["raw_response", "last_synced_at", "updated_at"])
    return response


def extract_first_message_id(response):
    try:
        return response["data"]["recipients"][0]["message_id"]
    except (KeyError, IndexError, TypeError):
        return ""


def normalize_message_status(response):
    status_value = ((response.get("data") or {}).get("status") or SentDMMessageStatus.QUEUED).lower()
    if status_value in SentDMMessageStatus.values:
        return status_value
    return SentDMMessageStatus.QUEUED



WHATSAPP_CUSTOMER_SERVICE_WINDOW_HOURS = 24
FOLLOW_UP_MESSAGE_PURPOSE = "follow_up"
REPLY_MESSAGE_PURPOSE = "reply"
AUTOMATED_FOLLOW_UP_DAYS = (1, 3, 7, 14)
AUTOMATED_FOLLOW_UP_TEMPLATES = {
    1: "Hi [Name], this is [Business Name]. Just following up on your recent message. Are you still looking for help with this? Reply STOP to opt out.",
    3: "[Business Name]: Checking in to see if you still need help with your request. Reply when you are ready, or reply STOP to opt out.",
    7: "Hi [Name], this is [Business Name]. We are following up on your earlier message. Let us know if you would still like help. Reply STOP to opt out.",
    14: "[Business Name]: This is our final follow-up about your request. If you still need help, reply here anytime. Reply STOP to opt out.",
}


def lead_has_active_whatsapp_window(lead, now=None):
    if not lead or not lead.last_incoming_at:
        return False
    now = now or timezone.now()
    return lead.last_incoming_at >= now - timedelta(hours=WHATSAPP_CUSTOMER_SERVICE_WINDOW_HOURS)


def resolve_outbound_channel(*, profile=None, requested_channel=SentDMChannel.AUTO, purpose="direct", lead=None, now=None):
    channel = requested_channel or SentDMChannel.AUTO
    if channel not in SentDMChannel.values:
        raise ValidationError({"channel": "Unsupported Sent.dm channel."})

    agent_whatsapp_active = is_agent_whatsapp_active(profile)

    if purpose == FOLLOW_UP_MESSAGE_PURPOSE and channel in {SentDMChannel.AUTO, SentDMChannel.WHATSAPP}:
        if not lead_has_active_whatsapp_window(lead, now=now):
            return SentDMChannel.SMS

    if channel == SentDMChannel.AUTO and profile and not agent_whatsapp_active:
        return SentDMChannel.SMS

    if channel == SentDMChannel.WHATSAPP:
        if not agent_whatsapp_active:
            if purpose in {REPLY_MESSAGE_PURPOSE, FOLLOW_UP_MESSAGE_PURPOSE}:
                return SentDMChannel.SMS
            raise ValidationError(
                {
                    "whatsapp": "WhatsApp is not active for this Sender Profile. Connect and verify the agent's own Meta WhatsApp Business Account first, or send with SMS/RCS."
                }
            )
        if purpose == FOLLOW_UP_MESSAGE_PURPOSE and not lead_has_active_whatsapp_window(lead, now=now):
            return SentDMChannel.SMS

    return channel


def get_follow_up_contact_name(lead):
    if getattr(lead, "full_name", ""):
        return lead.full_name
    contact = getattr(lead, "contact", None)
    if contact and contact.full_name:
        return contact.full_name
    return "there"


def render_automated_follow_up_message(followup):
    lead = followup.lead
    business_name = getattr(followup.organization, "name", "") or "Chesera"
    contact_name = get_follow_up_contact_name(lead)
    template = AUTOMATED_FOLLOW_UP_TEMPLATES.get(followup.sequence_day, AUTOMATED_FOLLOW_UP_TEMPLATES[14])
    return (
        template.replace("[Name]", contact_name)
        .replace("[Business Name]", business_name)
        .strip()
    )


def normalize_follow_up_requested_channel(channel):
    channel_value = (channel or SentDMChannel.SMS).strip().lower()
    if channel_value == SentDMChannel.WHATSAPP:
        return SentDMChannel.WHATSAPP
    if channel_value == SentDMChannel.RCS:
        return SentDMChannel.RCS
    return SentDMChannel.SMS


def schedule_automated_follow_ups_for_lead(lead, requested_channel="sms", base_time=None):
    if not lead or lead.is_opted_out:
        return []

    base_time = base_time or lead.last_incoming_at or timezone.now()
    requested_channel = normalize_follow_up_requested_channel(requested_channel)
    created_followups = []

    for sequence_day in AUTOMATED_FOLLOW_UP_DAYS:
        followup, created = AutomatedFollowUp.objects.get_or_create(
            lead=lead,
            sequence_day=sequence_day,
            defaults={
                "organization": lead.organization,
                "scheduled_time": base_time + timedelta(days=sequence_day),
                "requested_channel": requested_channel,
                "metadata": {"source": "sentdm_auto_capture"},
            },
        )
        if created:
            created_followups.append(followup)

    if created_followups:
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivityType.FOLLOW_UP_SCHEDULED,
            title="Automated follow-up sequence scheduled",
            description="Chesera scheduled backend-controlled follow-ups for Day 1, Day 3, Day 7, and Day 14.",
            metadata={
                "followup_ids": [str(item.id) for item in created_followups],
                "sequence_days": list(AUTOMATED_FOLLOW_UP_DAYS),
                "requested_channel": requested_channel,
            },
        )
        from notifications.services import NotificationTemplates, safe_notify

        safe_notify(NotificationTemplates.automated_followups_scheduled, lead, created_followups)

    return created_followups


def send_sentdm_message(*, user, to, text, profile=None, channel="auto", idempotency_prefix="message", purpose="direct", lead=None):
    channel = resolve_outbound_channel(profile=profile, requested_channel=channel, purpose=purpose, lead=lead)
    client = SentDMClient()
    response = client.send_message(
        to=to,
        text=text,
        profile_id=profile.profile_id if profile else None,
        channel=channel,
        idempotency_key=f"chesera-{idempotency_prefix}-{user.id}-{int(time.time())}",
    )

    message = SentDMMessage.objects.create(
        organization=profile.organization if profile else getattr(user, "organization", None),
        profile=profile,
        sent_message_id=extract_first_message_id(response),
        direction=SentDMMessageDirection.OUTBOUND,
        channel=channel,
        to_number=to,
        body=text,
        status=normalize_message_status(response),
        sandbox=getattr(settings, "SENTDM_SANDBOX_MODE", True),
        raw_response=response,
    )
    return message, response


def send_sandbox_message(*, user, to, text, profile=None, channel="auto", purpose="direct", lead=None):
    return send_sentdm_message(
        user=user,
        to=to,
        text=text,
        profile=profile,
        channel=channel,
        idempotency_prefix="sandbox-message",
        purpose=purpose,
        lead=lead,
    )


def send_live_message(*, user, to, text, profile=None, channel="auto", purpose="direct", lead=None):
    return send_sentdm_message(
        user=user,
        to=to,
        text=text,
        profile=profile,
        channel=channel,
        idempotency_prefix="live-message",
        purpose=purpose,
        lead=lead,
    )


def get_active_conversation_for_lead(lead):
    return Conversation.objects.filter(
        organization=lead.organization,
        lead=lead,
        status=ConversationStatus.ACTIVE,
    ).order_by("-last_message_at", "-created_at").first()


def get_follow_up_profile(followup):
    profile = getattr(followup.organization, "sentdm_profile", None)
    if profile:
        return profile
    return SentDMProfile.objects.filter(organization=followup.organization).first()


def fail_automated_follow_up(followup, error_message):
    now = timezone.now()
    followup.follow_up_status = AutomatedFollowUpStatus.FAILED
    followup.failed_at = now
    followup.error_message = str(error_message)
    followup.save(update_fields=["follow_up_status", "failed_at", "error_message", "updated_at"])
    LeadActivity.objects.create(
        lead=followup.lead,
        activity_type=LeadActivityType.FOLLOW_UP_FAILED,
        title=f"Day {followup.sequence_day} follow-up failed",
        description=str(error_message),
        metadata={"followup_id": str(followup.id), "sequence_day": followup.sequence_day},
    )
    from notifications.services import NotificationTemplates, safe_notify

    safe_notify(NotificationTemplates.automated_followup_failed, followup)
    return {"sent": False, "followup_id": followup.id, "error": str(error_message)}


def send_automated_follow_up(followup):
    if followup.follow_up_status != AutomatedFollowUpStatus.SCHEDULED:
        return {"sent": False, "followup_id": followup.id, "reason": "not_scheduled"}

    lead = followup.lead
    if lead.is_opted_out:
        followup.follow_up_status = AutomatedFollowUpStatus.CANCELED
        followup.error_message = "Lead is opted out."
        followup.save(update_fields=["follow_up_status", "error_message", "updated_at"])
        return {"sent": False, "followup_id": followup.id, "reason": "lead_opted_out"}

    profile = get_follow_up_profile(followup)
    if not profile or not profile.phone_number:
        return fail_automated_follow_up(followup, "Chesera SMS/RCS number is not assigned for this lead's organization.")

    conversation = get_active_conversation_for_lead(lead)
    if not conversation:
        return fail_automated_follow_up(followup, "No active conversation found for this lead.")

    try:
        channel = resolve_outbound_channel(
            profile=profile,
            requested_channel=followup.requested_channel or SentDMChannel.SMS,
            purpose=FOLLOW_UP_MESSAGE_PURPOSE,
            lead=lead,
        )
        text = render_automated_follow_up_message(followup)
        response = SentDMClient().send_message(
            to=lead.contact_number,
            text=text,
            profile_id=profile.profile_id,
            channel=channel,
            idempotency_key=f"chesera-followup-{followup.id}",
        )
    except (ImproperlyConfigured, SentDMClientError, ValidationError) as exc:
        return fail_automated_follow_up(followup, exc)

    now = timezone.now()
    message_id = extract_first_message_id(response) or f"sentdm-followup-{followup.id}"
    sentdm_status = normalize_message_status(response)
    from_number = profile.whatsapp_phone_number if channel == SentDMChannel.WHATSAPP and profile.whatsapp_phone_number else profile.phone_number

    SentDMMessage.objects.create(
        organization=followup.organization,
        profile=profile,
        lead=lead,
        conversation=conversation,
        sent_message_id=message_id,
        direction=SentDMMessageDirection.OUTBOUND,
        channel=channel,
        from_number=from_number,
        to_number=lead.contact_number,
        body=text,
        status=sentdm_status,
        sandbox=getattr(settings, "SENTDM_SANDBOX_MODE", True),
        raw_response=response,
    )
    Message.objects.get_or_create(
        provider_message_sid=message_id,
        defaults={
            "lead": lead,
            "conversation": conversation,
            "direction": MessageDirection.OUTBOUND,
            "sender": from_number[:20],
            "recipient": lead.contact_number[:20],
            "content": text,
            "provider_status": sentdm_status,
            "status": MessageStatus.QUEUED if sentdm_status == SentDMMessageStatus.QUEUED else MessageStatus.SENT,
            "metadata": {
                "source": "sentdm",
                "automated_followup": True,
                "followup_id": str(followup.id),
                "sequence_day": followup.sequence_day,
                "channel": channel,
                "requested_channel": followup.requested_channel,
            },
        },
    )

    followup.follow_up_status = AutomatedFollowUpStatus.SENT
    followup.resolved_channel = channel
    followup.message_body = text
    followup.sentdm_message_id = message_id
    followup.sent_at = now
    followup.error_message = ""
    followup.save(
        update_fields=[
            "follow_up_status",
            "resolved_channel",
            "message_body",
            "sentdm_message_id",
            "sent_at",
            "error_message",
            "updated_at",
        ]
    )

    lead.last_message_at = now
    lead.last_outgoing_at = now
    lead.save(update_fields=["last_message_at", "last_outgoing_at", "updated_at"])
    conversation.total_messages += 1
    conversation.last_message_at = now
    conversation.save(update_fields=["total_messages", "last_message_at", "updated_at"])

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivityType.FOLLOW_UP_SENT,
        title=f"Day {followup.sequence_day} follow-up sent",
        description="Chesera sent an automated backend-controlled follow-up message.",
        metadata={
            "followup_id": str(followup.id),
            "sequence_day": followup.sequence_day,
            "channel": channel,
            "sentdm_message_id": message_id,
        },
    )
    from notifications.services import NotificationTemplates, safe_notify

    safe_notify(NotificationTemplates.automated_followup_sent, followup)
    return {"sent": True, "followup_id": followup.id, "message_id": message_id, "channel": channel}


def send_due_automated_follow_ups(limit=50):
    due_followups = (
        AutomatedFollowUp.objects.select_related("organization", "organization__owner", "lead", "lead__contact")
        .filter(
            follow_up_status=AutomatedFollowUpStatus.SCHEDULED,
            scheduled_time__lte=timezone.now(),
            lead__is_opted_out=False,
        )
        .order_by("scheduled_time")[:limit]
    )

    results = []
    for followup in due_followups:
        results.append(send_automated_follow_up(followup))
    return {"processed": len(results), "results": results}


WEBHOOK_VALUE_CONTAINERS = ("payload", "data", "message", "event", "contact", "sender", "recipient")


def _first_scalar_value(payload, keys):
    if not isinstance(payload, dict):
        return ""

    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}) and not isinstance(value, (dict, list)):
            return str(value).strip()

    for key in WEBHOOK_VALUE_CONTAINERS:
        value = payload.get(key)
        if isinstance(value, dict):
            found = _first_scalar_value(value, keys)
            if found:
                return found
    return ""


def extract_sentdm_webhook_message(payload):
    profile_id = _first_scalar_value(payload, ("profile_id", "profileId", "sender_profile_id", "senderProfileId"))
    message_id = _first_scalar_value(payload, ("message_id", "messageId", "id", "sid"))
    event_type = _first_scalar_value(payload, ("sub_type", "subType", "type", "event_type", "eventType", "event"))
    direction = _first_scalar_value(payload, ("direction",)).lower()
    channel = _first_scalar_value(payload, ("channel", "preferred_channel")) or SentDMChannel.AUTO
    body = _first_scalar_value(payload, ("text", "body", "message", "content"))
    from_number = _first_scalar_value(
        payload,
        ("from_number", "fromNumber", "from", "sender", "sender_number", "senderNumber", "contact_number", "contactNumber", "customer_number", "customerNumber", "inbound_number", "inboundNumber"),
    )
    to_number = _first_scalar_value(
        payload,
        ("to_number", "toNumber", "to", "recipient", "recipient_number", "recipientNumber", "business_number", "businessNumber", "outbound_number", "outboundNumber"),
    )

    return {
        "profile_id": profile_id,
        "message_id": message_id,
        "event_type": event_type,
        "direction": direction,
        "channel": channel.lower(),
        "body": body,
        "from_number": from_number,
        "to_number": to_number,
    }


def is_inbound_message_webhook(event, details):
    haystack = " ".join(
        str(value or "").lower()
        for value in (event.event_type, details.get("event_type"), details.get("direction"))
    )
    return "message.received" in haystack or "received" in haystack or details.get("direction") == "inbound"


def get_control_keyword(text):
    first_word = "".join(char for char in (text or "").strip().split(" ", 1)[0].upper() if char.isalpha())
    if first_word in OPT_OUT_KEYWORDS or first_word in HELP_KEYWORDS:
        return first_word
    return ""


def get_profile_for_webhook(details):
    profile_id = details.get("profile_id")
    if profile_id:
        profile = SentDMProfile.objects.filter(profile_id=profile_id).select_related("organization", "user").first()
        if profile:
            return profile

    candidates = [details.get("to_number"), details.get("from_number")]
    return SentDMProfile.objects.filter(
        phone_number__in=[number for number in candidates if number]
    ).select_related("organization", "user").first() or SentDMProfile.objects.filter(
        whatsapp_phone_number__in=[number for number in candidates if number]
    ).select_related("organization", "user").first()


def get_or_create_business_phone(profile, organization, details):
    candidates = [details.get("to_number"), profile.phone_number if profile else "", profile.whatsapp_phone_number if profile else ""]
    for number in [candidate for candidate in candidates if candidate]:
        phone = PhoneNumber.objects.filter(organization=organization, phone_number=number).first()
        if phone:
            return phone

    number = next((candidate for candidate in candidates if candidate), "")
    if not number:
        return None

    provider_sid = f"sentdm:{profile.profile_id if profile else number}"[:100]
    is_primary = not PhoneNumber.objects.filter(organization=organization, is_primary=True).exists()
    existing_phone = PhoneNumber.objects.filter(phone_number=number).first()
    if existing_phone:
        return existing_phone if existing_phone.organization_id == organization.id else None

    phone = PhoneNumber.objects.create(
        phone_number=number,
        organization=organization,
        provider_phone_sid=provider_sid,
        status=PhoneNumberStatus.ACTIVE,
        is_primary=is_primary,
        capabilities={"sms": True, "rcs": True, "whatsapp": bool(profile and profile.whatsapp_phone_number == number)},
        metadata={"source": "sentdm_webhook", "profile_id": profile.profile_id if profile else ""},
    )
    return phone


def get_or_create_lead_and_conversation(profile, details):
    organization = profile.organization if profile else None
    if not organization or not details.get("from_number"):
        return None, None

    business_phone = get_or_create_business_phone(profile, organization, details)
    if not business_phone:
        return None, None

    now = timezone.now()
    contact, _ = Contact.objects.get_or_create(
        organization=organization,
        contact_number=details["from_number"],
        defaults={
            "phone_number": details["from_number"],
            "source": LeadSource.AUTO_CAPTURE,
            "metadata": {"source": "sentdm", "channel": details.get("channel", "auto")},
        },
    )
    lead, lead_created = Lead.objects.get_or_create(
        organization=organization,
        contact_number=details["from_number"],
        defaults={"business_phone": business_phone, "contact": contact, "source": LeadSource.AUTO_CAPTURE},
    )
    if not lead.contact_id:
        lead.contact = contact
    if not contact.linked_lead_id:
        contact.linked_lead = lead
        contact.save(update_fields=["linked_lead", "updated_at"])
    if lead_created:
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivityType.CREATED,
            title="Lead created",
            description="Contact was auto-captured from an inbound message.",
            metadata={"source": LeadSource.AUTO_CAPTURE, "channel": details.get("channel", "auto")},
        )
        from notifications.services import NotificationTemplates, safe_notify
        safe_notify(NotificationTemplates.new_lead_captured, lead, details.get("channel", "auto"))
        schedule_automated_follow_ups_for_lead(
            lead,
            requested_channel=details.get("channel", SentDMChannel.SMS),
            base_time=now,
        )
    lead.last_message_at = now
    lead.last_incoming_at = now
    lead_update_fields = ["last_message_at", "last_incoming_at", "updated_at"]
    if lead.contact_id:
        lead_update_fields.append("contact")
    lead.save(update_fields=lead_update_fields)

    conversation = Conversation.objects.filter(
        organization=organization,
        lead=lead,
        status=ConversationStatus.ACTIVE,
    ).first()
    if not conversation:
        conversation = Conversation.objects.create(
            organization=organization,
            lead=lead,
            status=ConversationStatus.ACTIVE,
            last_message_at=now,
        )
    else:
        conversation.last_message_at = now
        conversation.unread_messages += 1
        conversation.save(update_fields=["last_message_at", "unread_messages", "updated_at"])

    return lead, conversation


def store_inbound_sentdm_message(event, profile, lead, conversation, details):
    message_id = details.get("message_id") or f"sentdm-webhook-{event.pk}"
    sentdm_message = SentDMMessage.objects.filter(
        sent_message_id=message_id,
        direction=SentDMMessageDirection.INBOUND,
    ).first()
    if not sentdm_message:
        sentdm_message = SentDMMessage.objects.create(
            organization=profile.organization if profile else None,
            profile=profile,
            lead=lead,
            conversation=conversation,
            sent_message_id=message_id,
            direction=SentDMMessageDirection.INBOUND,
            channel=details.get("channel") or SentDMChannel.AUTO,
            from_number=details.get("from_number", ""),
            to_number=details.get("to_number", ""),
            body=details.get("body", ""),
            status=SentDMMessageStatus.DELIVERED,
            sandbox=getattr(settings, "SENTDM_SANDBOX_MODE", True),
            raw_response=event.payload,
        )

    if lead and conversation:
        message, created = Message.objects.get_or_create(
            provider_message_sid=message_id,
            defaults={
                "lead": lead,
                "conversation": conversation,
                "direction": MessageDirection.INBOUND,
                "sender": details.get("from_number", "")[:20],
                "recipient": details.get("to_number", "")[:20],
                "content": details.get("body", ""),
                "provider_status": "received",
                "status": MessageStatus.DELIVERED,
                "metadata": {"source": "sentdm", "webhook_event_id": event.pk, "channel": details.get("channel", "auto")},
            },
        )
        if created:
            if not lead.activities.filter(activity_type=LeadActivityType.MESSAGE_RECEIVED).exists():
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type=LeadActivityType.MESSAGE_RECEIVED,
                    title="First reply received",
                    description="Lead sent the first inbound message to the Chesera number.",
                    metadata={"source": "sentdm", "channel": details.get("channel", "auto")},
                )
            conversation.total_messages += 1
            conversation.unread_messages += 1
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["total_messages", "unread_messages", "last_message_at", "updated_at"])

    return sentdm_message


def send_control_autoresponse(profile, lead, conversation, text, channel, kind):
    if not profile or not lead or not text:
        return None

    try:
        send_channel = resolve_outbound_channel(
            profile=profile,
            requested_channel=channel,
            purpose=REPLY_MESSAGE_PURPOSE,
            lead=lead,
        )
        response = SentDMClient().send_message(
            to=lead.contact_number,
            text=text,
            profile_id=profile.profile_id,
            channel=send_channel,
            idempotency_key=f"chesera-sentdm-{kind}-{lead.id}-{int(time.time())}",
        )
    except (ImproperlyConfigured, SentDMClientError, ValidationError):
        return None
    message_id = extract_first_message_id(response) or f"sentdm-{kind}-{lead.id}-{int(time.time())}"
    sentdm_message = SentDMMessage.objects.create(
        organization=profile.organization,
        profile=profile,
        lead=lead,
        conversation=conversation,
        sent_message_id=message_id,
        direction=SentDMMessageDirection.OUTBOUND,
        channel=send_channel or SentDMChannel.AUTO,
        from_number=profile.whatsapp_phone_number if send_channel == SentDMChannel.WHATSAPP and profile.whatsapp_phone_number else profile.phone_number,
        to_number=lead.contact_number,
        body=text,
        status=normalize_message_status(response),
        sandbox=getattr(settings, "SENTDM_SANDBOX_MODE", True),
        raw_response=response,
    )
    if conversation:
        Message.objects.get_or_create(
            provider_message_sid=message_id,
            defaults={
                "lead": lead,
                "conversation": conversation,
                "direction": MessageDirection.OUTBOUND,
                "sender": sentdm_message.from_number[:20],
                "recipient": lead.contact_number[:20],
                "content": text,
                "provider_status": sentdm_message.status,
                "status": MessageStatus.QUEUED if sentdm_message.status == SentDMMessageStatus.QUEUED else MessageStatus.SENT,
                "metadata": {"source": "sentdm", "control_response": kind, "channel": send_channel or "auto", "requested_channel": channel or "auto"},
            },
        )
        conversation.total_messages += 1
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["total_messages", "last_message_at", "updated_at"])
    return sentdm_message


def normalize_ai_stage(stage):
    stage_value = (stage or "").strip().lower()
    if stage_value == "cold":
        return LeadStage.COLD
    if stage_value == "warm":
        return LeadStage.WARM
    if stage_value == "hot":
        return LeadStage.HOT
    if stage_value in LeadStage.values:
        return stage_value
    return LeadStage.COLD




def send_ai_reply_for_inbound(profile, lead, conversation, channel):
    if not profile or not lead or not conversation:
        return {"sent": False, "reason": "missing_routing_context"}
    if lead.is_opted_out:
        return {"sent": False, "reason": "lead_opted_out"}
    if not lead.ai_enabled or not conversation.ai_enabled:
        return {"sent": False, "reason": "ai_disabled"}

    history = conversation.messages.order_by("created_at")
    ai_response = AIService().generate_reply_and_stage(history, organization=profile.organization)
    reply_text = (ai_response.get("reply") or "").strip()
    if not reply_text:
        return {"sent": False, "reason": "empty_ai_reply"}

    send_channel = resolve_outbound_channel(
        profile=profile,
        requested_channel=channel,
        purpose=REPLY_MESSAGE_PURPOSE,
        lead=lead,
    )
    response = SentDMClient().send_message(
        to=lead.contact_number,
        text=reply_text,
        profile_id=profile.profile_id,
        channel=send_channel,
        idempotency_key=f"chesera-sentdm-ai-{conversation.id}-{int(time.time())}",
    )
    message_id = extract_first_message_id(response) or f"sentdm-ai-{conversation.id}-{int(time.time())}"
    sentdm_status = normalize_message_status(response)
    from_number = profile.whatsapp_phone_number if send_channel == SentDMChannel.WHATSAPP and profile.whatsapp_phone_number else profile.phone_number

    sentdm_message = SentDMMessage.objects.create(
        organization=profile.organization,
        profile=profile,
        lead=lead,
        conversation=conversation,
        sent_message_id=message_id,
        direction=SentDMMessageDirection.OUTBOUND,
        channel=send_channel or SentDMChannel.AUTO,
        from_number=from_number,
        to_number=lead.contact_number,
        body=reply_text,
        status=sentdm_status,
        sandbox=getattr(settings, "SENTDM_SANDBOX_MODE", True),
        raw_response=response,
    )
    message_status = MessageStatus.QUEUED if sentdm_status == SentDMMessageStatus.QUEUED else MessageStatus.SENT
    Message.objects.get_or_create(
        provider_message_sid=message_id,
        defaults={
            "lead": lead,
            "conversation": conversation,
            "direction": MessageDirection.OUTBOUND,
            "sender": from_number[:20],
            "recipient": lead.contact_number[:20],
            "content": reply_text,
            "provider_status": sentdm_status,
            "status": message_status,
            "is_ai_generated": True,
            "metadata": {"source": "sentdm", "channel": send_channel or "auto", "requested_channel": channel or "auto", "ai_stage": ai_response.get("stage", "")},
        },
    )

    now = timezone.now()
    old_stage = lead.stage
    lead.stage = normalize_ai_stage(ai_response.get("stage"))
    lead.last_message_at = now
    lead.last_outgoing_at = now
    lead.last_ai_reply_at = now
    lead_update_fields = ["stage", "last_message_at", "last_outgoing_at", "last_ai_reply_at", "updated_at"]
    if lead.stage == LeadStage.HOT:
        lead.ai_enabled = False
        lead.handed_over_at = lead.handed_over_at or now
        lead_update_fields.extend(["ai_enabled", "handed_over_at"])
        conversation.ai_enabled = False
    lead.save(update_fields=lead_update_fields)
    if old_stage != lead.stage:
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivityType.STAGE_CHANGED,
            title=f"Status changed to {lead.get_stage_display()}",
            description=f"Lead status changed from {old_stage} to {lead.stage}.",
            metadata={"from": old_stage, "to": lead.stage, "source": "ai"},
        )
    ai_activity_title = "AI welcome sent" if not lead.activities.filter(activity_type=LeadActivityType.AI_REPLIED).exists() else "AI reply sent"
    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivityType.AI_REPLIED,
        title=ai_activity_title,
        description="Chesera AI sent an automated reply.",
        metadata={"source": "sentdm", "channel": send_channel or "auto"},
    )

    conversation.total_messages += 1
    conversation.last_message_at = now
    conversation_update_fields = ["total_messages", "last_message_at", "updated_at"]
    if not conversation.ai_enabled:
        conversation_update_fields.append("ai_enabled")
    conversation.save(update_fields=conversation_update_fields)

    return {"sent": True, "message_id": sentdm_message.sent_message_id, "stage": lead.stage}

def apply_opt_out(lead, keyword):
    now = timezone.now()
    lead.is_opted_out = True
    lead.opted_out_at = lead.opted_out_at or now
    lead.opt_out_keyword = keyword
    lead.opt_out_source = "sentdm"
    lead.ai_enabled = False
    lead.save(update_fields=["is_opted_out", "opted_out_at", "opt_out_keyword", "opt_out_source", "ai_enabled", "updated_at"])
    Conversation.objects.filter(lead=lead, status=ConversationStatus.ACTIVE).update(
        status=ConversationStatus.CLOSED,
        ai_enabled=False,
        closed_at=now,
        updated_at=now,
    )
    FollowUpReminder.objects.filter(lead=lead, is_sent=False).update(is_sent=True, updated_at=now)
    AutomatedFollowUp.objects.filter(
        lead=lead,
        follow_up_status=AutomatedFollowUpStatus.SCHEDULED,
    ).update(
        follow_up_status=AutomatedFollowUpStatus.CANCELED,
        error_message=f"Lead opted out with {keyword}.",
        updated_at=now,
    )


def process_sentdm_webhook_event(event):
    try:
        with transaction.atomic():
            details = extract_sentdm_webhook_message(event.payload)
            if details.get("profile_id") and not event.profile_id:
                event.profile_id = details["profile_id"]
                event.save(update_fields=["profile_id", "updated_at"])

            if not is_inbound_message_webhook(event, details):
                event.mark_processed()
                return {"processed": True, "action": "ignored_non_inbound", "details": details}

            profile = get_profile_for_webhook(details)
            lead, conversation = get_or_create_lead_and_conversation(profile, details)
            store_inbound_sentdm_message(event, profile, lead, conversation, details)

            keyword = get_control_keyword(details.get("body"))
            if lead and keyword in OPT_OUT_KEYWORDS:
                apply_opt_out(lead, keyword)
                text = profile.organization.sentdm_opt_out_confirmation_message if profile and profile.organization else "You have been unsubscribed and will not receive more messages."
                send_control_autoresponse(profile, lead, conversation, text, details.get("channel"), "optout")
                event.mark_processed()
                return {"processed": True, "action": "opt_out", "keyword": keyword, "lead_id": lead.id}

            if lead and keyword in HELP_KEYWORDS:
                organization = profile.organization if profile else lead.organization
                text = organization.sentdm_help_response_message or f"{organization.name}: Contact {organization.sentdm_support_email or organization.email} for support. Reply STOP to opt out."
                send_control_autoresponse(profile, lead, conversation, text, details.get("channel"), "help")
                event.mark_processed()
                return {"processed": True, "action": "help", "keyword": keyword, "lead_id": lead.id}

            try:
                ai_result = send_ai_reply_for_inbound(profile, lead, conversation, details.get("channel"))
            except Exception as exc:
                ai_result = {"sent": False, "reason": "ai_reply_failed", "error": str(exc)}
            event.mark_processed()
            return {
                "processed": True,
                "action": "ai_reply_sent" if ai_result.get("sent") else ai_result.get("reason", "stored_inbound"),
                "lead_id": lead.id if lead else None,
                "ai": ai_result,
            }
    except (ImproperlyConfigured, SentDMClientError, Exception) as exc:
        event.status = SentDMWebhookEventStatus.FAILED
        event.error_message = str(exc)
        event.save(update_fields=["status", "error_message", "updated_at"])
        return {"processed": False, "action": "failed", "error": str(exc)}

def enqueue_sentdm_webhook_event(event):
    if not getattr(settings, "SENTDM_WEBHOOK_ASYNC_ENABLED", True) or getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        result = process_sentdm_webhook_event(event)
        return {"queued": False, "processed_inline": True, "result": result}

    try:
        from .tasks import process_sentdm_webhook_event_task

        async_result = process_sentdm_webhook_event_task.delay(event.pk)
        return {"queued": True, "task_id": async_result.id, "processed_inline": False}
    except Exception as exc:
        event.status = SentDMWebhookEventStatus.FAILED
        event.error_message = f"Failed to enqueue webhook event: {exc}"
        event.save(update_fields=["status", "error_message", "updated_at"])
        return {"queued": False, "processed_inline": False, "error": str(exc)}

def verify_webhook_signature(request):
    secret = getattr(settings, "SENTDM_WEBHOOK_SECRET", "")
    if not secret:
        return False

    signature = request.headers.get("x-webhook-signature", "")
    webhook_id = request.headers.get("x-webhook-id", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")

    if not signature or not webhook_id or not timestamp:
        return False

    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        return False

    if age > getattr(settings, "SENTDM_WEBHOOK_TOLERANCE_SECONDS", 300):
        return False

    secret_value = secret.removeprefix("whsec_")
    try:
        secret_key = base64.b64decode(secret_value, validate=True)
    except (binascii.Error, ValueError):
        secret_key = secret.encode()

    signed_content = webhook_id.encode() + b"." + timestamp.encode() + b"." + request.body
    digest = hmac.new(secret_key, signed_content, hashlib.sha256).digest()
    expected = f"v1,{base64.b64encode(digest).decode()}"
    return hmac.compare_digest(signature, expected)


def create_webhook_event(request, *, allow_unverified_in_debug=False):
    signature_verified = verify_webhook_signature(request)
    if not signature_verified and not (allow_unverified_in_debug and settings.DEBUG):
        return None, False

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {"raw": request.body.decode("utf-8", errors="ignore")}

    event = SentDMWebhookEvent.objects.create(
        event_id=request.headers.get("x-webhook-id", ""),
        event_type=request.headers.get("x-webhook-event-type", payload.get("type", "")),
        profile_id=payload.get("profile_id") or payload.get("profileId") or "",
        signature_verified=signature_verified,
        payload=payload,
        headers={key: value for key, value in request.headers.items()},
    )
    return event, True


def get_active_welcome_template(user, organization):
    return StaticMessageTemplate.objects.filter(
        user=user,
        organization=organization,
        template_type=MessageTemplateType.WELCOME,
        is_active=True,
    ).first()


def render_contact_template(template_text, contact, organization):
    business_name = getattr(organization, "name", "") or "Chesera"
    full_name = contact.full_name or "there"
    return (
        str(template_text or "")
        .replace("[Name]", full_name)
        .replace("[name]", full_name)
        .replace("[Business]", business_name)
        .replace("[business]", business_name)
        .replace("[Agent Business]", business_name)
    ).strip()


def send_welcome_message_to_contact(contact_id):
    contact = Contact.objects.select_related("organization", "organization__owner").filter(pk=contact_id).first()
    if not contact:
        return {"sent": False, "reason": "contact_not_found"}

    organization = contact.organization
    user = organization.owner
    settings_obj = getattr(organization, "settings", None)
    if not settings_obj or not getattr(settings_obj, "auto_welcome_message_enabled", False):
        return {"sent": False, "reason": "auto_welcome_disabled"}

    template = get_active_welcome_template(user, organization)
    if not template or not template.message.strip():
        return {"sent": False, "reason": "welcome_template_missing"}

    profile = getattr(organization, "sentdm_profile", None) or SentDMProfile.objects.filter(organization=organization).first()
    if not profile or not profile.phone_number:
        return {"sent": False, "reason": "chesera_number_not_assigned"}

    text = render_contact_template(template.message, contact, organization)
    if not text:
        return {"sent": False, "reason": "welcome_template_empty"}

    try:
        message, response = send_sentdm_message(
            user=user,
            to=contact.contact_number,
            text=text,
            profile=profile,
            channel=SentDMChannel.SMS,
            idempotency_prefix=f"welcome-contact-{contact.id}",
            purpose="welcome",
        )
    except Exception as exc:
        metadata = dict(contact.metadata or {})
        metadata["welcome_message"] = {"status": "failed", "error": str(exc), "updated_at": timezone.now().isoformat()}
        contact.metadata = metadata
        contact.save(update_fields=["metadata", "updated_at"])
        return {"sent": False, "reason": "send_failed", "error": str(exc)}

    metadata = dict(contact.metadata or {})
    metadata["welcome_message"] = {
        "status": message.status,
        "sentdm_message_id": message.sent_message_id,
        "sent_at": timezone.now().isoformat(),
    }
    contact.metadata = metadata
    contact.save(update_fields=["metadata", "updated_at"])
    return {"sent": True, "message_id": message.sent_message_id, "status": message.status}
