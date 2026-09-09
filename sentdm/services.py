import base64
import binascii
import hashlib
import hmac
import json
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from business.models import PhoneNumber, PhoneNumberStatus
from communications.choices import ConversationStatus, MessageDirection, MessageStatus
from communications.models import Conversation, Message
from crm.models import FollowUpReminder, Lead

from .choices import SentDMChannel, SentDMCampaignStatus, SentDMMessageDirection, SentDMMessageStatus, SentDMProfileStatus, SentDMWebhookEventStatus
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
    lead, _ = Lead.objects.get_or_create(
        organization=organization,
        contact_number=details["from_number"],
        defaults={"business_phone": business_phone},
    )
    lead.last_message_at = now
    lead.last_incoming_at = now
    lead.save(update_fields=["last_message_at", "last_incoming_at", "updated_at"])

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
            conversation.total_messages += 1
            conversation.unread_messages += 1
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["total_messages", "unread_messages", "last_message_at", "updated_at"])

    return sentdm_message


def send_control_autoresponse(profile, lead, conversation, text, channel, kind):
    if not profile or not lead or not text:
        return None

    try:
        response = SentDMClient().send_message(
            to=lead.contact_number,
            text=text,
            profile_id=profile.profile_id,
            channel=channel if channel in SentDMChannel.values and channel != SentDMChannel.AUTO else None,
            idempotency_key=f"chesera-sentdm-{kind}-{lead.id}-{int(time.time())}",
        )
    except (ImproperlyConfigured, SentDMClientError):
        return None
    message_id = extract_first_message_id(response) or f"sentdm-{kind}-{lead.id}-{int(time.time())}"
    sentdm_message = SentDMMessage.objects.create(
        organization=profile.organization,
        profile=profile,
        lead=lead,
        conversation=conversation,
        sent_message_id=message_id,
        direction=SentDMMessageDirection.OUTBOUND,
        channel=channel or SentDMChannel.AUTO,
        from_number=profile.phone_number or profile.whatsapp_phone_number,
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
                "metadata": {"source": "sentdm", "control_response": kind, "channel": channel or "auto"},
            },
        )
        conversation.total_messages += 1
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["total_messages", "last_message_at", "updated_at"])
    return sentdm_message


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

            event.mark_processed()
            return {"processed": True, "action": "stored_inbound", "lead_id": lead.id if lead else None}
    except (ImproperlyConfigured, SentDMClientError, Exception) as exc:
        event.status = SentDMWebhookEventStatus.FAILED
        event.error_message = str(exc)
        event.save(update_fields=["status", "error_message", "updated_at"])
        return {"processed": False, "action": "failed", "error": str(exc)}
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
