from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import User
from ai.ai_service import AIService


class DummyAIConfiguration:
    model_name = "gpt-test"
    system_prompt = "Only answer questions about active buyer leads."
    temperature = 0.25
    max_tokens = 500
    top_p = 1.0


class DummyBusinessSettings:
    reply_tone = "professional"


class DummyOrganization:
    name = "Example Realty"
    sentdm_legal_name = "Example Realty LLC"
    sentdm_support_email = "support@example.com"
    sentdm_vertical = "REAL_ESTATE"
    sentdm_messaging_use_case = "Lead replies and appointment follow-ups for opted-in real estate leads."
    ai_configuration = DummyAIConfiguration()
    settings = DummyBusinessSettings()


class AICompliancePromptTests(SimpleTestCase):
    def test_system_prompt_contains_sentdm_compliance_rules_and_business_context(self):
        prompt = AIService().build_system_prompt(organization=DummyOrganization())

        self.assertIn("Example Realty LLC", prompt)
        self.assertIn("support@example.com", prompt)
        self.assertIn("REAL_ESTATE", prompt)
        self.assertIn("Lead replies and appointment follow-ups", prompt)
        self.assertIn("Reply STOP to opt out", prompt)
        self.assertIn("Do not use urgency", prompt)
        self.assertIn("Do not use ALL CAPS", prompt)
        self.assertIn("Do not use excessive punctuation", prompt)
        self.assertIn("Do not use link shorteners", prompt)
        self.assertIn("Stay strictly within the approved messaging use case", prompt)
        self.assertIn("Only answer questions about active buyer leads.", prompt)

    def test_fallback_reply_identifies_business_and_includes_stop_language(self):
        result = AIService().generate_reply_and_stage([], organization=DummyOrganization())

        self.assertEqual(result["stage"], "HOT")
        self.assertIn("Example Realty LLC", result["reply"])
        self.assertIn("Reply STOP to opt out", result["reply"])


class StructuredMessageAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+15558889999", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("ai.views.AIService")
    def test_structured_message_endpoint_is_stateless(self, mocked_service):
        mocked_service.return_value.generate_structured_message.return_value = {
            "tone": "friendly",
            "structured_msg": "Hi Alex, thanks for reaching out. I can help with that.",
        }

        response = self.client.post(
            "/api/v1/ai/messages/structure/",
            {"tone": "friendly", "msg": "hey alex i can help"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["data"]["structured_msg"], "Hi Alex, thanks for reaching out. I can help with that.")
        mocked_service.return_value.generate_structured_message.assert_called_once_with(tone="friendly", msg="hey alex i can help")

    def test_structured_message_service_fallback_cleans_message(self):
        result = AIService().generate_structured_message(tone="professional", msg=" hello   there ")

        self.assertEqual(result["tone"], "professional")
        self.assertEqual(result["structured_msg"], "hello there.")