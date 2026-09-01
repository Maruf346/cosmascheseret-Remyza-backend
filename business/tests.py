from django.test import TestCase

from accounts.models import User
from business.models import Organization
from business.serializers import OrganizationSerializer


class OrganizationWhatsAppConfigSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            phone_number="+15550001001",
            email="agent@example.com",
            full_name="Agent Example",
        )
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Example Realty",
            sentdm_whatsapp_waba_id="123456789012345",
            sentdm_whatsapp_phone_number_id="987654321098765",
            sentdm_whatsapp_access_token="EAAxxxxxxxxxxxxxxx",
        )

    def test_serializer_hides_whatsapp_access_token(self):
        data = OrganizationSerializer(self.organization).data

        self.assertTrue(data["has_sentdm_whatsapp_config"])
        self.assertEqual(data["sentdm_whatsapp_waba_id"], "123456789012345")
        self.assertEqual(data["sentdm_whatsapp_phone_number_id"], "987654321098765")
        self.assertNotIn("sentdm_whatsapp_access_token", data)

    def test_partial_whatsapp_config_is_rejected(self):
        organization = Organization.objects.create(
            owner=User.objects.create(phone_number="+15550001002"),
            name="Partial Realty",
        )
        serializer = OrganizationSerializer(
            organization,
            data={"sentdm_whatsapp_waba_id": "123456789012345"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("sentdm_whatsapp", serializer.errors)