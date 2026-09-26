import base64
import hashlib
import hmac
import time
from unittest.mock import patch
from types import SimpleNamespace

from datetime import timedelta

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from business.models import Organization, PhoneNumber
from communications.choices import ConversationStatus
from crm.choices import LeadStage
from communications.models import Conversation, Message
from crm.models import Contact, FollowUpReminder, Lead
from subscription.models import UserSubscription

from .choices import SentDMChannel, SentDMWhatsAppConnectionSource, SentDMWhatsAppConnectionStatus
from .client import SentDMClient, SentDMClientError
from .models import SentDMMessage, SentDMProfile, SentDMWebhookEvent
from .services import build_10dlc_campaign_payload, build_profile_payload, FOLLOW_UP_MESSAGE_PURPOSE, lead_has_active_whatsapp_window, connect_agent_whatsapp_for_user, get_sentdm_profile_creation_readiness, normalize_message_status, normalize_profile_status, process_sentdm_webhook_event, resolve_outbound_channel, send_live_message, upsert_profile_from_response, verify_webhook_signature
from .tasks import process_sentdm_webhook_event_task
from .views import SentDMInboundWebhookAPIView, SentDMProfileCreateAPIView, SentDMProfileListAPIView, SentDMWhatsAppConnectAPIView, SentDMSendMessageAPIView, SentDMSendSandboxMessageAPIView


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

    @patch("sentdm.client.requests.request")
    @override_settings(SENTDM_SANDBOX_MODE=False)
    def test_send_message_uses_documented_free_text_payload_shape(self, mocked_request):
        mocked_request.return_value.status_code = 202
        mocked_request.return_value.headers = {"X-Request-Id": "req_test"}
        mocked_request.return_value.json.return_value = {
            "success": True,
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_test"}]},
        }
        client = SentDMClient(api_key="test-key", base_url="https://api.sent.dm/v3")

        response = client.send_message(to="+15551234567", text="Hello", profile_id="profile_test", channel="sms")

        self.assertTrue(response["success"])
        mocked_request.assert_called_once()
        kwargs = mocked_request.call_args.kwargs
        self.assertEqual(kwargs["json"], {"to": ["+15551234567"], "text": "Hello", "channel": ["sms"]})
        self.assertEqual(kwargs["headers"]["x-profile-id"], "profile_test")

    @patch("sentdm.client.requests.request")
    @override_settings(SENTDM_SANDBOX_MODE=False)
    def test_send_message_omits_channel_for_auto_routing(self, mocked_request):
        mocked_request.return_value.status_code = 202
        mocked_request.return_value.headers = {}
        mocked_request.return_value.json.return_value = {
            "success": True,
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_auto"}]},
        }
        client = SentDMClient(api_key="test-key", base_url="https://api.sent.dm/v3")

        client.send_message(to="+15551234567", text="Hello", channel="auto")

        self.assertEqual(mocked_request.call_args.kwargs["json"], {"to": ["+15551234567"], "text": "Hello"})
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


    def test_profile_creation_readiness_warns_when_direct_whatsapp_credentials_are_missing(self):
        class User:
            id = 11
            full_name = "Agent Example"
            phone_number = "+15551234567"
            email = "agent@example.com"
            organization = None

        class Organization:
            sentdm_legal_name = "Example Realty LLC"
            sentdm_support_email = "support@example.com"
            sentdm_privacy_policy_url = "https://example.com/privacy"
            sentdm_terms_url = "https://example.com/terms"
            sentdm_opt_in_description = "Lead submits a form and agrees to receive replies."
            sentdm_messaging_use_case = "Customer care replies for opted-in real estate leads."
            sentdm_messaging_use_case_us = "CUSTOMER_CARE"
            sentdm_sample_message_1 = "Example Realty: Thanks for reaching out. Reply STOP to opt out."
            sentdm_sample_message_2 = ""
            sentdm_sample_message_3 = ""
            sentdm_opt_in_confirmation_message = "Example Realty: Thanks for opting in. Reply STOP to opt out."
            sentdm_opt_out_confirmation_message = "Example Realty: You have been unsubscribed."
            sentdm_help_response_message = "Example Realty: Contact support@example.com. Reply STOP to opt out."
            sentdm_whatsapp_waba_id = ""
            sentdm_whatsapp_phone_number_id = ""
            sentdm_whatsapp_access_token = ""

        user = User()
        user.organization = Organization()

        readiness = get_sentdm_profile_creation_readiness(user)

        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["has_direct_whatsapp_business_account"])
        self.assertIn("organization-level WhatsApp Business Account", readiness["warnings"][0])

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


class SentDMOutboundChannelPolicyTests(SimpleTestCase):
    def test_auto_without_agent_whatsapp_routes_to_sms(self):
        profile = SimpleNamespace(is_agent_whatsapp_active=False)

        self.assertEqual(resolve_outbound_channel(profile=None, requested_channel=SentDMChannel.AUTO), SentDMChannel.AUTO)
        self.assertEqual(resolve_outbound_channel(profile=profile, requested_channel=SentDMChannel.AUTO), SentDMChannel.SMS)
        self.assertEqual(resolve_outbound_channel(profile=profile, requested_channel=SentDMChannel.SMS), SentDMChannel.SMS)
        self.assertEqual(resolve_outbound_channel(profile=profile, requested_channel=SentDMChannel.RCS), SentDMChannel.RCS)

    def test_explicit_whatsapp_requires_agent_owned_active_whatsapp(self):
        inherited_profile = SimpleNamespace(is_agent_whatsapp_active=False, whatsapp_phone_number="+15559990000")

        with self.assertRaises(ValidationError):
            resolve_outbound_channel(profile=inherited_profile, requested_channel=SentDMChannel.WHATSAPP)

    def test_follow_up_whatsapp_inside_customer_service_window_can_use_direct_whatsapp(self):
        now = timezone.now()
        profile = SimpleNamespace(is_agent_whatsapp_active=True, whatsapp_phone_number="+15559990000")
        lead = SimpleNamespace(last_incoming_at=now - timedelta(hours=23, minutes=59))

        self.assertTrue(lead_has_active_whatsapp_window(lead, now=now))
        self.assertEqual(
            resolve_outbound_channel(
                profile=profile,
                requested_channel=SentDMChannel.WHATSAPP,
                purpose=FOLLOW_UP_MESSAGE_PURPOSE,
                lead=lead,
                now=now,
            ),
            SentDMChannel.WHATSAPP,
        )

    def test_follow_up_whatsapp_outside_customer_service_window_routes_to_sms(self):
        now = timezone.now()
        profile = SimpleNamespace(is_agent_whatsapp_active=True, whatsapp_phone_number="+15559990000")
        lead = SimpleNamespace(last_incoming_at=now - timedelta(days=3))

        self.assertFalse(lead_has_active_whatsapp_window(lead, now=now))
        self.assertEqual(
            resolve_outbound_channel(
                profile=profile,
                requested_channel=SentDMChannel.WHATSAPP,
                purpose=FOLLOW_UP_MESSAGE_PURPOSE,
                lead=lead,
                now=now,
            ),
            SentDMChannel.SMS,
        )

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

    @override_settings(SENTDM_SANDBOX_MODE=False)
    @patch("sentdm.services.SentDMClient")
    def test_follow_up_send_routes_whatsapp_request_to_sms_outside_24_hour_window(self, mocked_client):
        mocked_client.return_value.send_message.return_value = {
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_follow_up_sms"}]}
        }
        profile = SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_with_whatsapp",
            name="Profile With WhatsApp",
            phone_number="+15559990000",
            whatsapp_phone_number="+15558880000",
        )
        business_phone = PhoneNumber.objects.create(
            organization=self.organization,
            phone_number="+15559990000",
            provider_phone_sid="sentdm-follow-up-test",
            is_primary=True,
        )
        lead = Lead.objects.create(
            organization=self.organization,
            business_phone=business_phone,
            contact_number="+15551234567",
            last_incoming_at=timezone.now() - timedelta(days=3),
        )

        message, _ = send_live_message(
            user=self.user,
            to=lead.contact_number,
            text="Following up from Example Realty. Reply STOP to opt out.",
            profile=profile,
            channel=SentDMChannel.WHATSAPP,
            purpose=FOLLOW_UP_MESSAGE_PURPOSE,
            lead=lead,
        )

        self.assertEqual(message.channel, SentDMChannel.SMS)
        self.assertEqual(mocked_client.return_value.send_message.call_args.kwargs["channel"], SentDMChannel.SMS)

class SentDMWhatsAppConnectionStateTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create(
            phone_number="+15550002000",
            email="whatsapp-owner@example.com",
            full_name="WhatsApp Owner",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="WhatsApp Realty",
            email="team-whatsapp@example.com",
        )
        UserSubscription.objects.create(
            user=self.user,
            organization=self.organization,
            product_id="chesera.monthly",
            plan_type="monthly",
            medium="apple",
            transaction_id="txn-whatsapp-connect",
            is_subscription_active=True,
            expiry_date=timezone.now() + timedelta(days=30),
        )

    def test_inherited_whatsapp_response_does_not_activate_agent_whatsapp(self):
        profile = upsert_profile_from_response(
            {
                "data": {
                    "id": "profile_inherited_whatsapp",
                    "name": "Inherited Profile",
                    "status": "completed",
                    "sending_phone_number": "+15559990000",
                    "whatsapp_phone_number": "+15558880000",
                }
            },
            user=self.user,
            organization=self.organization,
            direct_whatsapp_requested=False,
        )

        self.assertEqual(profile.whatsapp_connection_source, SentDMWhatsAppConnectionSource.INHERITED)
        self.assertEqual(profile.whatsapp_connection_status, SentDMWhatsAppConnectionStatus.NOT_CONNECTED)
        self.assertEqual(profile.whatsapp_phone_number, "")
        self.assertFalse(profile.is_agent_whatsapp_active)
        self.assertEqual(resolve_outbound_channel(profile=profile, requested_channel=SentDMChannel.AUTO), SentDMChannel.SMS)

    def test_direct_whatsapp_response_activates_agent_whatsapp(self):
        profile = upsert_profile_from_response(
            {
                "data": {
                    "id": "profile_direct_whatsapp",
                    "name": "Direct Profile",
                    "status": "completed",
                    "sending_phone_number": "+15559990000",
                    "whatsapp_phone_number": "+15558880000",
                }
            },
            user=self.user,
            organization=self.organization,
            direct_whatsapp_requested=True,
        )

        self.assertEqual(profile.whatsapp_connection_source, SentDMWhatsAppConnectionSource.DIRECT)
        self.assertEqual(profile.whatsapp_connection_status, SentDMWhatsAppConnectionStatus.ACTIVE)
        self.assertEqual(profile.whatsapp_phone_number, "+15558880000")
        self.assertTrue(profile.is_agent_whatsapp_active)
        self.assertEqual(resolve_outbound_channel(profile=profile, requested_channel=SentDMChannel.WHATSAPP), SentDMChannel.WHATSAPP)

    @patch("sentdm.services.SentDMClient")
    def test_connect_agent_whatsapp_updates_profile_and_stores_credentials(self, mocked_client):
        mocked_client.return_value.update_profile.return_value = {
            "data": {
                "id": "profile_connect_success",
                "name": "Connect Profile",
                "status": "completed",
                "sending_phone_number": "+15559990000",
                "whatsapp_phone_number": "+15558880000",
            }
        }
        SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_connect_success",
            name="Connect Profile",
        )

        profile, _ = connect_agent_whatsapp_for_user(
            self.user,
            {
                "waba_id": "123456789012345",
                "phone_number_id": "987654321098765",
                "access_token": "EAAxxxxxxxxxxxxxxx",
            },
        )

        self.assertTrue(profile.is_agent_whatsapp_active)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.sentdm_whatsapp_waba_id, "123456789012345")
        self.assertEqual(mocked_client.return_value.update_profile.call_args.args[0], "profile_connect_success")
        self.assertEqual(
            mocked_client.return_value.update_profile.call_args.args[1]["whatsapp_business_account"]["phone_number_id"],
            "987654321098765",
        )

    @patch("sentdm.services.SentDMClient")
    def test_connect_agent_whatsapp_failure_marks_profile_failed(self, mocked_client):
        mocked_client.return_value.update_profile.side_effect = SentDMClientError("Invalid WABA credentials", status_code=422)
        profile = SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_connect_failed",
            name="Connect Failed Profile",
        )

        with self.assertRaises(SentDMClientError):
            connect_agent_whatsapp_for_user(
                self.user,
                {
                    "waba_id": "bad-waba",
                    "phone_number_id": "bad-phone",
                    "access_token": "bad-token",
                },
            )

        profile.refresh_from_db()
        self.assertEqual(profile.whatsapp_connection_source, SentDMWhatsAppConnectionSource.DIRECT)
        self.assertEqual(profile.whatsapp_connection_status, SentDMWhatsAppConnectionStatus.FAILED)
        self.assertIn("Invalid WABA credentials", profile.whatsapp_connection_error)

    @patch("sentdm.views.connect_agent_whatsapp_for_user")
    def test_whatsapp_connect_endpoint_returns_updated_profile(self, mocked_connect):
        profile = SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_endpoint_success",
            name="Endpoint Profile",
            whatsapp_phone_number="+15558880000",
            whatsapp_connection_source=SentDMWhatsAppConnectionSource.DIRECT,
            whatsapp_connection_status=SentDMWhatsAppConnectionStatus.ACTIVE,
        )
        mocked_connect.return_value = (profile, {"success": True, "data": {"id": profile.profile_id}})
        request = self.factory.post(
            "/api/v1/sentdm/profiles/whatsapp/connect/",
            {
                "profile_id": profile.profile_id,
                "waba_id": "123456789012345",
                "phone_number_id": "987654321098765",
                "access_token": "EAAxxxxxxxxxxxxxxx",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = SentDMWhatsAppConnectAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["profile"]["is_agent_whatsapp_active"])
        mocked_connect.assert_called_once()

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

    @patch("sentdm.services.SentDMClient")
    @patch("sentdm.services.AIService")
    def test_regular_inbound_webhook_sends_ai_reply(self, mocked_ai_service, mocked_client):
        mocked_ai_service.return_value.generate_reply_and_stage.return_value = {
            "reply": "Hi there, thanks for reaching out. Reply STOP to opt out.",
            "stage": "WARM",
        }
        mocked_client.return_value.send_message.return_value = {
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_ai_reply"}]}
        }
        event = self.create_message_event(text="I need help buying a home", message_id="msg_ai_in")

        result = process_sentdm_webhook_event(event)

        lead = Lead.objects.get(organization=self.organization, contact_number="+15551112222")
        conversation = Conversation.objects.get(organization=self.organization, lead=lead)
        contact = Contact.objects.get(organization=self.organization, contact_number="+15551112222")
        outbound_message = Message.objects.get(provider_message_sid="msg_ai_reply")
        event.refresh_from_db()

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "ai_reply_sent")
        self.assertEqual(lead.stage, LeadStage.WARM)
        self.assertEqual(lead.contact, contact)
        self.assertEqual(contact.linked_lead, lead)
        self.assertTrue(lead.ai_enabled)
        self.assertTrue(conversation.ai_enabled)
        self.assertTrue(outbound_message.is_ai_generated)
        self.assertEqual(outbound_message.content, "Hi there, thanks for reaching out. Reply STOP to opt out.")
        self.assertTrue(SentDMMessage.objects.filter(sent_message_id="msg_ai_reply", lead=lead).exists())
        self.assertEqual(event.status, "processed")
        mocked_ai_service.return_value.generate_reply_and_stage.assert_called_once()
        self.assertEqual(mocked_ai_service.return_value.generate_reply_and_stage.call_args.kwargs["organization"], self.organization)
        mocked_client.return_value.send_message.assert_called_once()
        self.assertEqual(mocked_client.return_value.send_message.call_args.kwargs["channel"], "sms")

    @patch("sentdm.services.SentDMClient")
    @patch("sentdm.services.AIService")
    def test_opted_out_lead_does_not_trigger_ai_reply(self, mocked_ai_service, mocked_client):
        Lead.objects.create(
            organization=self.organization,
            business_phone=self.business_phone,
            contact_number="+15551112222",
            is_opted_out=True,
            ai_enabled=False,
        )
        event = self.create_message_event(text="Hello again", message_id="msg_opted_out_in")

        result = process_sentdm_webhook_event(event)

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "lead_opted_out")
        self.assertEqual(result["ai"]["reason"], "lead_opted_out")
        mocked_ai_service.assert_not_called()
        mocked_client.return_value.send_message.assert_not_called()

    @patch("sentdm.services.SentDMClient")
    @patch("sentdm.services.AIService")
    def test_hot_ai_reply_disables_ai_for_handoff(self, mocked_ai_service, mocked_client):
        mocked_ai_service.return_value.generate_reply_and_stage.return_value = {
            "reply": "I will have the agent follow up with you. Reply STOP to opt out.",
            "stage": "HOT",
        }
        mocked_client.return_value.send_message.return_value = {
            "data": {"status": "QUEUED", "recipients": [{"message_id": "msg_hot_reply"}]}
        }
        event = self.create_message_event(text="I am ready to book", message_id="msg_hot_in")

        result = process_sentdm_webhook_event(event)

        lead = Lead.objects.get(organization=self.organization, contact_number="+15551112222")
        conversation = Conversation.objects.get(organization=self.organization, lead=lead)

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "ai_reply_sent")
        self.assertEqual(lead.stage, LeadStage.HOT)
        self.assertFalse(lead.ai_enabled)
        self.assertIsNotNone(lead.handed_over_at)
        self.assertFalse(conversation.ai_enabled)
class SentDMWebhookAsyncQueueTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=True, SENTDM_WEBHOOK_ASYNC_ENABLED=True)
    @patch("sentdm.views.enqueue_sentdm_webhook_event")
    def test_inbound_webhook_stores_event_and_queues_processing(self, mocked_enqueue):
        mocked_enqueue.return_value = {"queued": True, "task_id": "task-123", "processed_inline": False}
        request = self.factory.post(
            "/api/v1/sentdm/webhooks/inbound/",
            b'{"type":"message.received","payload":{"profile_id":"profile_test","text":"hello"}}',
            content_type="application/json",
            HTTP_X_WEBHOOK_ID="webhook-endpoint-id",
            HTTP_X_WEBHOOK_EVENT_TYPE="message.received",
        )

        response = SentDMInboundWebhookAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["processing"]["queued"])
        event = SentDMWebhookEvent.objects.get()
        self.assertEqual(event.status, "received")
        mocked_enqueue.assert_called_once_with(event)

    def test_process_task_skips_already_processed_event(self):
        event = SentDMWebhookEvent.objects.create(
            event_type="message.received",
            status="processed",
            payload={"type": "message.received"},
        )

        result = process_sentdm_webhook_event_task(event.id)

        self.assertTrue(result["processed"])
        self.assertEqual(result["action"], "already_processed")
