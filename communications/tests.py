from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from business.models import Organization


class WelcomeMessageTemplateDisabledAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+15557770001", password="pass12345", email="welcome@example.com")
        self.organization = Organization.objects.create(owner=self.user, name="Welcome Realty")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_welcome_message_template_endpoint_is_hidden(self):
        response = self.client.put(
            "/api/v1/message-templates/welcome/",
            {"subject": "Welcome", "message": "Hi [Name], thanks for connecting with [Business].", "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_welcome_message_template_patch_endpoint_is_hidden(self):
        response = self.client.patch(
            "/api/v1/message-templates/welcome/",
            {"message": "New welcome message"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)