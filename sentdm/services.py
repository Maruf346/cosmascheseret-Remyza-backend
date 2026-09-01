import hashlib
import hmac
import json
import time

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .choices import SentDMCampaignStatus, SentDMMessageDirection, SentDMMessageStatus, SentDMProfileStatus
from .client import SentDMClient
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
def build_profile_payload(organization, user, overrides=None):
    overrides = overrides or {}
    name = getattr(organization, "name", "") or user.full_name or user.phone_number
    email = getattr(organization, "email", "") or user.email or ""
    legal_name = getattr(organization, "sentdm_legal_name", "") or name
    support_email = getattr(organization, "sentdm_support_email", "") or email
    authorized_rep_name = getattr(organization, "sentdm_authorized_rep_name", "") or user.full_name or name
    vertical = getattr(organization, "sentdm_vertical", "") or "PROFESSIONAL"

    payload = {
        "name": overrides.get("name") or name,
        "short_name": overrides.get("short_name") or build_short_name(name, fallback=f"USR{user.id}"),
        "description": overrides.get("description") or f"Chesera messaging profile for {name}",
        "email": overrides.get("email") or support_email,
        "inherit_contacts": False,
        "inherit_templates": False,
        "billing_model": "organization",
    }

    whatsapp_business_account = get_sentdm_whatsapp_business_account(organization)
    if whatsapp_business_account:
        payload["whatsapp_business_account"] = whatsapp_business_account

    website = getattr(organization, "website", "")
    if website or support_email:
        payload["brand"] = {
            "contact": {
                "name": authorized_rep_name,
                "businessName": legal_name,
                "email": overrides.get("email") or support_email,
            },
            "business": {
                "legalName": legal_name,
                "country": getattr(organization, "country", "US") or "US",
            },
            "compliance": {
                "vertical": vertical,
                "brandRelationship": "SMALL_ACCOUNT",
                "isTcrApplication": True,
            },
        }
    return payload

def upsert_profile_from_response(response, *, user=None, organization=None):
    data = response.get("data") or {}
    profile_id = data.get("id")
    if not profile_id:
        return None

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
            "whatsapp_phone_number": data.get("whatsapp_phone_number") or "",
            "billing_model": data.get("billing_model") or "organization",
            "inherit_contacts": bool(data.get("inherit_contacts", False)),
            "inherit_templates": bool(data.get("inherit_templates", False)),
            "inherit_tcr_brand": bool(data.get("inherit_tcr_brand", True)),
            "inherit_tcr_campaign": bool(data.get("inherit_tcr_campaign", True)),
            "sandbox": getattr(settings, "SENTDM_SANDBOX_MODE", True),
            "last_synced_at": timezone.now(),
            "raw_response": response,
        },
    )
    return profile


def create_profile_for_user(user, profile_data=None):
    organization = getattr(user, "organization", None)
    payload = build_profile_payload(organization, user, overrides=profile_data)
    client = SentDMClient()
    response = client.create_profile(payload, idempotency_key=f"chesera-profile-user-{user.id}")
    profile = upsert_profile_from_response(response, user=user, organization=organization)
    return profile, response



SENTDM_10DLC_REQUIRED_FIELDS = {
    "sentdm_legal_name": "Legal business name is required for 10DLC registration.",
    "sentdm_support_email": "Support email is required for HELP autoresponses.",
    "sentdm_privacy_policy_url": "Privacy Policy URL is required for 10DLC registration.",
    "sentdm_terms_url": "Terms and Conditions URL is required for 10DLC registration.",
    "sentdm_opt_in_description": "Opt-in/message-flow description is required for 10DLC registration.",
    "sentdm_messaging_use_case": "Campaign description/use case is required for 10DLC registration.",
    "sentdm_messaging_use_case_us": "US messaging use-case value is required for 10DLC registration.",
    "sentdm_sample_message_1": "At least one realistic sample message is required for 10DLC registration.",
    "sentdm_opt_in_confirmation_message": "Opt-in confirmation autoresponse is required for 10DLC registration.",
    "sentdm_opt_out_confirmation_message": "Opt-out confirmation autoresponse is required for 10DLC registration.",
    "sentdm_help_response_message": "HELP autoresponse is required for 10DLC registration.",
}
SENTDM_SAMPLE_FIELDS = ("sentdm_sample_message_1", "sentdm_sample_message_2", "sentdm_sample_message_3")
SENTDM_TWO_SAMPLE_USE_CASES = {"MARKETING", "MIXED", "LOW_VOLUME"}


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
        "description": organization.sentdm_messaging_use_case,
        "type": campaign_type or "App",
        "useCases": [
            {
                "messagingUseCaseUs": use_case,
                "sampleMessages": get_sentdm_sample_messages(organization),
            }
        ],
        "messageFlow": organization.sentdm_opt_in_description,
        "privacyPolicyLink": organization.sentdm_privacy_policy_url,
        "termsAndConditionsLink": organization.sentdm_terms_url,
        "optinMessage": organization.sentdm_opt_in_confirmation_message,
        "optoutMessage": organization.sentdm_opt_out_confirmation_message,
        "helpMessage": organization.sentdm_help_response_message,
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


def send_sentdm_message(*, user, to, text, profile=None, channel="auto", idempotency_prefix="message"):
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


def send_sandbox_message(*, user, to, text, profile=None, channel="auto"):
    return send_sentdm_message(
        user=user,
        to=to,
        text=text,
        profile=profile,
        channel=channel,
        idempotency_prefix="sandbox-message",
    )


def send_live_message(*, user, to, text, profile=None, channel="auto"):
    return send_sentdm_message(
        user=user,
        to=to,
        text=text,
        profile=profile,
        channel=channel,
        idempotency_prefix="live-message",
    )


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

    signed_content = webhook_id.encode() + b"." + timestamp.encode() + b"." + request.body
    expected = hmac.new(secret.encode(), signed_content, hashlib.sha256).hexdigest()
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
