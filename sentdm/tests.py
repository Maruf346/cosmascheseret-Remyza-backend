import hashlib
import hmac
import time

from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .client import SentDMClient
from .services import normalize_message_status, normalize_profile_status, verify_webhook_signature
from .views import SentDMSendMessageAPIView, SentDMSendSandboxMessageAPIView


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


class SentDMSendModeGuardTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = DummyUser()

    @override_settings(SENTDM_SANDBOX_MODE=False)
    def test_sandbox_send_endpoint_rejects_live_mode(self):
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
    def test_live_send_endpoint_rejects_sandbox_mode(self):
        request = self.factory.post(
            "/api/v1/sentdm/messages/send/",
            {"to": "+15551234567", "text": "hello"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = SentDMSendMessageAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("sandbox", response.data)


class SentDMWebhookSignatureTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(SENTDM_WEBHOOK_SECRET="secret", SENTDM_WEBHOOK_TOLERANCE_SECONDS=300)
    def test_verify_webhook_signature_accepts_valid_signature(self):
        body = b'{"type":"message.received"}'
        timestamp = str(int(time.time()))
        webhook_id = "evt_123"
        signature = hmac.new(
            b"secret",
            webhook_id.encode() + b"." + timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        request = self.factory.post(
            "/api/v1/sentdm/webhooks/inbound/",
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_ID=webhook_id,
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        )

        self.assertTrue(verify_webhook_signature(request))

    @override_settings(SENTDM_WEBHOOK_SECRET="secret", SENTDM_WEBHOOK_TOLERANCE_SECONDS=300)
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