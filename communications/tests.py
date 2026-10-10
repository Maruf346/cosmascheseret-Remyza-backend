from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from business.models import Organization
from communications.choices import MessageTemplateType
from communications.models import StaticMessageTemplate


class WelcomeMessagePresetAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+15557770001", password="pass12345", email="welcome@example.com")
        self.organization = Organization.objects.create(owner=self.user, name="Welcome Realty")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_legacy_free_form_welcome_endpoint_is_hidden(self):
        response = self.client.put(
            "/api/v1/message-templates/welcome/",
            {"subject": "Welcome", "message": "Custom free-form welcome text.", "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_list_welcome_presets(self):
        response = self.client.get("/api/v1/welcome-message/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual({item["key"] for item in data["templates"]}, {"professional", "friendly", "casual"})
        self.assertIsNone(data["selected"])

    def test_get_single_welcome_preset(self):
        response = self.client.get("/api/v1/welcome-message/?template=professional")

        self.assertEqual(response.status_code, 200, response.content)
        template = response.json()["data"]["template"]
        self.assertEqual(template["key"], "professional")
        self.assertIn("Reply STOP to opt out", template["message"])

    def test_invalid_welcome_preset_returns_400(self):
        response = self.client.get("/api/v1/welcome-message/?template=anything")

        self.assertEqual(response.status_code, 400, response.content)

    def test_select_welcome_preset_creates_static_template(self):
        response = self.client.put("/api/v1/welcome-message/", {"template": "friendly"}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["template"], "friendly")
        saved = StaticMessageTemplate.objects.get(
            organization=self.organization,
            user=self.user,
            template_type=MessageTemplateType.WELCOME,
        )
        self.assertEqual(saved.subject, "Friendly Welcome Message")
        self.assertEqual(saved.message, data["message"])

    def test_update_selected_welcome_preset(self):
        self.client.put("/api/v1/welcome-message/", {"template": "friendly"}, format="json")

        response = self.client.patch("/api/v1/welcome-message/", {"template": "casual"}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["template"], "casual")
        self.assertEqual(StaticMessageTemplate.objects.count(), 1)
        self.assertEqual(StaticMessageTemplate.objects.get().subject, "Casual Welcome Message")

    def test_custom_message_text_is_not_accepted(self):
        response = self.client.put(
            "/api/v1/welcome-message/",
            {"template": "friendly", "message": "Please use my custom text instead."},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotEqual(StaticMessageTemplate.objects.get().message, "Please use my custom text instead.")