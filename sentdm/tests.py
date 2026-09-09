import base64
import hashlib
import hmac
import time
from unittest.mock import patch

from datetime import timedelta

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from business.models import Organization, PhoneNumber
from communications.choices import ConversationStatus
from communications.models import Conversation, Message
from crm.models import FollowUpReminder, Lead
from subscription.models import UserSubscription

from .client import SentDMClient, SentDMClientError
from .models import SentDMProfile, SentDMWebhookEvent
from .services import build_10dlc_campaign_payload, build_profile_payload, normalize_message_status, normalize_profile_status, process_sentdm_webhook_event, verify_webhook_signature
from .views import SentDMProfileCreateAPIView, SentDMProfileListAPIView, SentDMSendMessageAPIView, SentDMSendSandboxMessageAPIView


class DummyUser:
    is_authenticated = True
    id = 1


class SentDMClientSandboxTests(SimpleTestCase):
    @override_settings(SENTDM_SANDBOX_MODE=True)
    def test_with_sandbox_adds_sandbox_flag(self):
        client = SentDMClient(api_key="test-key", base_url="https://api.sent.dm/v3")

        payload = client.with_sandbox({"text": "hello"})

        self.assertEqual(payload, {"text": "hello", "sandbox": True})

    @override_settings(SENTDM_SANDBOX_MODE=False)
    def test_with_sandbox_leaves_live_payload_unchanged(self):
        client = SentDMClient(api_key="test-key", base_url="https://api.sent.dm/v3")

        payload = client.with_sandbox({"text": "hello"})

        self.assertEqual(payload, {"text": "hello"})

    def test_build_profile_payload_uses_request_overrides(self):
        class User:
            id = 7
            full_name = ""
            phone_number = "+15551234567"
            email = ""

        payload = build_profile_payload(
            None,
            User(),
            overrides={
                "name": "Test Sender Profile",
                "short_name": "testSender",
                "description": "description is here",
                "email": "user@example.com",
            },
        )

        self.assertEqual(payload["name"], "Test Sender Profile")
        self.assertEqual(payload["short_name"], "testSender")
        self.assertEqual(payload["description"], "description is here")
        self.assertEqual(payload["email"], "user@example.com")



    def test_build_10dlc_campaign_payload_uses_compliance_fields(self):
        class Organization:
            name = "Remyza Realty"
            sentdm_messaging_use_case = "Lead replies and appointment follow-ups for opted-in real estate leads."
            sentdm_messaging_use_case_us = "CUSTOMER_CARE"
            sentdm_expected_daily_volume = 250
            sentdm_sample_message_1 = "Remyza Realty: Thanks for reaching out about the property. Reply STOP to opt out."
            sentdm_sample_message_2 = ""
            sentdm_sample_message_3 = ""
            sentdm_opt_in_description = "Lead submits a website form and agrees to receive SMS replies from Remyza Realty."
            sentdm_privacy_policy_url = "https://example.com/privacy"
            sentdm_terms_url = "https://example.com/terms"
            sentdm_opt_in_confirmation_message = "Remyza Realty: Thanks for opting in. Reply HELP for help or STOP to opt out. Msg and data rates may apply."
            sentdm_opt_out_confirmation_message = "Remyza Realty: You have been unsubscribed and will not receive more messages."
            sentdm_help_response_message = "Remyza Realty: Contact support@example.com for support. Reply STOP to opt out."

        payload = build_10dlc_campaign_payload(Organization())
        campaign = payload["campaign"]

        self.assertEqual(campaign["name"], "Remyza Realty Customer Messaging")
        self.assertEqual(campaign["volume"], "250")
        self.assertEqual(campaign["useCases"][0]["messagingUseCaseUs"], "CUSTOMER_CARE")
        self.assertEqual(len(campaign["useCases"][0]["sampleMessages"]), 1)
        self.assertEqual(campaign["optoutKeywords"], "STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT")

class SentDMSendModeGuardTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = DummyUser()

    @override_settings(SENTDM_SANDBOX_MODE=False)
    @patch("sentdm.permissions.SubscriptionValidationService.get_paid_active_subscription", return_value=object())
    def test_sandbox_send_endpoint_rejects_live_mode(self, mocked_subscription):
        request = self.factory.post(
            "/api/v1/sentdm/messages/send-sandbox/",
            {"to": "+15551234567", "text": "hello"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = SentDMSendSandboxMessageAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("sandbox", response.data)

    @override_settings(SENTDM_SANDBOX_MODE=True)
    @patch("sentdm.permissions.SubscriptionValidationService.get_paid_active_subscription", return_value=object())
    def test_live_send_endpoint_rejects_sandbox_mode(self, mocked_subscription):
        request = self.factory.post(
            "/api/v1/sentdm/messages/send/",
            {"to": "+15551234567", "text": "hello"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = SentDMSendMessageAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("sandbox", response.data)



class SentDMPaidSubscriptionPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = DummyUser()

    @patch("sentdm.permissions.SubscriptionValidationService.get_paid_active_subscription", return_value=None)
    def test_sentdm_control_endpoint_requires_paid_subscription(self, mocked_subscription):
        request = self.factory.get("/api/v1/sentdm/profiles/")
        force_authenticate(request, user=self.user)

        response = SentDMProfileListAPIView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn("paid subscription", str(response.data["detail"]))
        mocked_subscription.assert_called_once_with(self.user)


class SentDMWebhookSignatureTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(SENTDM_WEBHOOK_SECRET="whsec_c2VjcmV0", SENTDM_WEBHOOK_TOLERANCE_SECONDS=300)
    def test_verify_webhook_signature_accepts_valid_signature(self):
        body = b'{"type":"message.received"}'
        timestamp = str(int(time.time()))
        webhook_id = "evt_123"
        digest = hmac.new(
            b"secret",
            webhook_id.encode() + b"." + timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).digest()
        signature = f"v1,{base64.b64encode(digest).decode()}"
        request = self.factory.post(
            "/api/v1/sentdm/webhooks/inbound/",
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_ID=webhook_id,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )

        self.assertTrue(verify_webhook_signature(request))

    @override_settings(SENTDM_WEBHOOK_SECRET="whsec_c2VjcmV0", SENTDM_WEBHOOK_TOLERANCE_SECONDS=300)
    def test_verify_webhook_signature_rejects_invalid_signature(self):
        request = self.factory.post(
            "/api/v1/sentdm/webhooks/inbound/",
            b'{"type":"message.received"}',
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="bad-signature",
            HTTP_X_WEBHOOK_ID="evt_123",
            HTTP_X_WEBHOOK_TIMESTAMP=str(int(time.time())),
        )

        self.assertFalse(verify_webhook_signature(request))


class SentDMStatusTests(SimpleTestCase):
    def test_normalize_profile_status_maps_completed_to_approved(self):
        self.assertEqual(normalize_profile_status("COMPLETED"), "approved")

    def test_normalize_profile_status_falls_back_for_unknown_values(self):
        self.assertEqual(normalize_profile_status("unexpected"), "incomplete")

    def test_normalize_message_status_falls_back_for_unknown_values(self):
        self.assertEqual(normalize_message_status({"data": {"status": "mystery"}}), "queued")
class SentDMProfileCreateGuardTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create(
            phone_number="+15550000001",
            email="agent@example.com",
            full_name="Test Agent",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Test Business",
            email="team@example.com",
        )
        UserSubscription.objects.create(
            user=self.user,
            organization=self.organization,
            product_id="chesera.monthly",
            plan_type="monthly",
            medium="apple",
            transaction_id="txn-profile-guard",
            is_subscription_active=True,
            expiry_date=timezone.now() + timedelta(days=30),
        )

    @patch("sentdm.services.SentDMClient")
    def test_create_profile_requires_business_compliance_fields(self, mocked_client):
        request = self.factory.post("/api/v1/sentdm/profiles/create/", {}, format="json")
        force_authenticate(request, user=self.user)

        response = SentDMProfileCreateAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("missing_fields", response.data)
        self.assertIn("sentdm_legal_name", response.data["missing_fields"])
        mocked_client.assert_not_called()

    @patch("sentdm.services.SentDMClient")
    def test_create_profile_rejects_existing_sender_profile(self, mocked_client):
        SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_existing",
            name="Existing Profile",
        )
        request = self.factory.post("/api/v1/sentdm/profiles/create/", {}, format="json")
        force_authenticate(request, user=self.user)

        response = SentDMProfileCreateAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["profile_id"], "profile_existing")
        mocked_client.assert_not_called()
    @override_settings(SENTDM_SANDBOX_MODE=False)
    @patch("sentdm.services.SentDMClient")
    def test_live_whatsapp_send_requires_active_whatsapp_number(self, mocked_client):
        SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_without_whatsapp",
            name="Profile Without WhatsApp",
            whatsapp_phone_number="",
        )
        request = self.factory.post(
            "/api/v1/sentdm/messages/send/",
            {
                "to": "+15551234567",
                "text": "hello",
                "profile_id": "profile_without_whatsapp",
                "channel": "whatsapp",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = SentDMSendMessageAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("whatsapp", response.data)
        mocked_client.assert_not_called()

class SentDMWhatsAppPayloadTests(SimpleTestCase):
    def test_build_profile_payload_includes_optional_whatsapp_business_account(self):
        class User:
            id = 9
            full_name = "Agent Example"
            phone_number = "+15551234567"
            email = "agent@example.com"

        class Organization:
            name = "Example Realty"
            email = "team@example.com"
            website = "https://example.com"
            country = "US"
            sentdm_legal_name = "Example Realty LLC"
            sentdm_support_email = "support@example.com"
            sentdm_authorized_rep_name = "Agent Example"
            sentdm_vertical = "REAL_ESTATE"
            sentdm_whatsapp_waba_id = "123456789012345"
            sentdm_whatsapp_phone_number_id = "987654321098765"
            sentdm_whatsapp_access_token = "EAAxxxxxxxxxxxxxxx"

        payload = build_profile_payload(Organization(), User())

        self.assertEqual(
            payload["whatsapp_business_account"],
            {
                "waba_id": "123456789012345",
                "phone_number_id": "987654321098765",
                "access_token": "EAAxxxxxxxxxxxxxxx",
            },
        )

    def test_build_profile_payload_omits_whatsapp_business_account_when_not_configured(self):
        class User:
            id = 10
            full_name = "Agent Example"
            phone_number = "+15551234567"
            email = "agent@example.com"

        class Organization:
            name = "Example Realty"
            email = "team@example.com"
            website = ""
            sentdm_legal_name = "Example Realty LLC"
            sentdm_support_email = "support@example.com"
            sentdm_authorized_rep_name = "Agent Example"
            sentdm_vertical = "REAL_ESTATE"
            sentdm_whatsapp_waba_id = ""
            sentdm_whatsapp_phone_number_id = ""
            sentdm_whatsapp_access_token = ""

        payload = build_profile_payload(Organization(), User())

        self.assertNotIn("whatsapp_business_account", payload)


class SentDMWebhookProcessingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+15550001000",
            email="owner@example.com",
            full_name="Owner Example",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Example Realty",
            email="team@example.com",
            sentdm_support_email="support@example.com",
            sentdm_opt_out_confirmation_message="Example Realty: You have been unsubscribed and will not receive more messages.",
            sentdm_help_response_message="Example Realty: Contact support@example.com for support. Reply STOP to opt out.",
        )
        self.business_phone = PhoneNumber.objects.create(
            organization=self.organization,
            phone_number="+15559990000",
            provider_phone_sid="sentdm-profile_test",
            is_primary=True,
        )
        self.profile = SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_test",
            name="Example Realty Profile",
            phone_number=self.business_phone.phone_number,
        )

    def create_message_event(self, *, text, message_id="msg_in_1"):
        return SentDMWebhookEvent.objects.create(
            event_type="message.received",
            profile_id=self.profile.profile_id,
            payload={
                "field": "message",
                "sub_type": "message.received",
                "payload": {
                    "profile_id": self.profile.profile_id,
                    "message_id": message_id,
                    "channel": "sms",
                    "inbound_number": "+15551112222",
                    "outbound_number": self.business_phone.phone_number,
                    "text": text,
                },
            },
            signature_verified=True,
        )

    @patch("sentdm.services.SentDMClient")
    def test_stop_webhook_opts_out_lead_closes_conversation_and_stops_reminders(self, mocked_client):
        mocked_client.return_value.send_message.return_value = {
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_stop_confirm"}]}
        }
        lead = Lead.objects.create(
            organization=self.organization,
            business_phone=self.business_phone,
            contact_number="+15551112222",
        )
        conversation = Conversation.objects.create(
            organization=self.organization,
            lead=lead,
            status=ConversationStatus.ACTIVE,
            ai_enabled=True,
        )
        reminder = FollowUpReminder.objects.create(
            organization=self.organization,
            lead=lead,
            scheduled_time=timezone.now(),
        )
        event = self.create_message_event(text="STOP", message_id="msg_stop_in")

        result = process_sentdm_webhook_event(event)

        lead.refresh_from_db()
        conversation.refresh_from_db()
        reminder.refresh_from_db()
        event.refresh_from_db()

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "opt_out")
        self.assertTrue(lead.is_opted_out)
        self.assertFalse(lead.ai_enabled)
        self.assertEqual(lead.opt_out_keyword, "STOP")
        self.assertEqual(conversation.status, ConversationStatus.CLOSED)
        self.assertFalse(conversation.ai_enabled)
        self.assertTrue(reminder.is_sent)
        self.assertEqual(event.status, "processed")
        self.assertTrue(Message.objects.filter(provider_message_sid="msg_stop_in").exists())
        self.assertTrue(Message.objects.filter(provider_message_sid="msg_stop_confirm").exists())
        mocked_client.return_value.send_message.assert_called_once()

    @patch("sentdm.services.SentDMClient")
    def test_stop_opt_out_persists_when_confirmation_send_fails(self, mocked_client):
        mocked_client.return_value.send_message.side_effect = SentDMClientError("provider unavailable")
        event = self.create_message_event(text="STOP", message_id="msg_stop_send_failed")

        result = process_sentdm_webhook_event(event)

        lead = Lead.objects.get(organization=self.organization, contact_number="+15551112222")
        event.refresh_from_db()

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "opt_out")
        self.assertTrue(lead.is_opted_out)
        self.assertFalse(lead.ai_enabled)
        self.assertEqual(event.status, "processed")
    @patch("sentdm.services.SentDMClient")
    def test_help_webhook_sends_help_response_without_opting_out(self, mocked_client):
        mocked_client.return_value.send_message.return_value = {
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_help_reply"}]}
        }
        event = self.create_message_event(text="HELP", message_id="msg_help_in")

        result = process_sentdm_webhook_event(event)

        lead = Lead.objects.get(organization=self.organization, contact_number="+15551112222")
        event.refresh_from_db()

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "help")
        self.assertFalse(lead.is_opted_out)
        self.assertTrue(lead.ai_enabled)
        self.assertEqual(event.status, "processed")
        self.assertTrue(Message.objects.filter(provider_message_sid="msg_help_in").exists())
        self.assertTrue(Message.objects.filter(provider_message_sid="msg_help_reply").exists())
        mocked_client.return_value.send_message.assert_called_once()