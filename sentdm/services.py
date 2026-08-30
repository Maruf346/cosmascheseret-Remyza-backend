import hashlib
import hmac
import json
import time

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .choices import SentDMMessageDirection, SentDMMessageStatus, SentDMProfileStatus
from .client import SentDMClient
from .models import SentDMMessage, SentDMProfile, SentDMWebhookEvent


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


def build_profile_payload(organization, user):
    name = getattr(organization, "name", "") or user.full_name or user.phone_number
    email = getattr(organization, "email", "") or user.email or ""

    payload = {
        "name": name,
        "short_name": build_short_name(name, fallback=f"USR{user.id}"),
        "description": f"Chesera messaging profile for {name}",
        "email": email,
        "inherit_contacts": False,
        "inherit_templates": False,
        "billing_model": "organization",
    }

    website = getattr(organization, "website", "")
    if website or email:
        payload["brand"] = {
            "contact": {
                "name": user.full_name or name,
                "businessName": name,
                "email": email,
            },
            "business": {
                "legalName": name,
                "country": getattr(organization, "country", "US") or "US",
            },
            "compliance": {
                "vertical": "PROFESSIONAL",
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


def create_profile_for_user(user):
    organization = getattr(user, "organization", None)
    payload = build_profile_payload(organization, user)
    client = SentDMClient()
    response = client.create_profile(payload, idempotency_key=f"chesera-profile-user-{user.id}")
    profile = upsert_profile_from_response(response, user=user, organization=organization)
    return profile, response


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