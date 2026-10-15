from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.choices import UserType
from accounts.models import User
from core.models import GeneralSettings
from core.views import AdminGeneralSettingsAPIView
from notifications.models import Notification, NotificationType


class AdminGeneralSettingsAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create(
            phone_number="+15550001000",
            email="admin-settings@example.com",
            full_name="Settings Admin",
            is_staff=True,
            user_type=UserType.ADMIN,
        )
        self.user = User.objects.create(
            phone_number="+15550001001",
            email="agent-settings@example.com",
            full_name="Settings Agent",
            user_type=UserType.CLIENT,
        )

    def test_get_creates_and_returns_single_general_settings_instance(self):
        request = self.factory.get("/api/v1/admin/settings/general/")
        force_authenticate(request, user=self.admin)

        response = AdminGeneralSettingsAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["app_name"], "Chesera")
        self.assertEqual(GeneralSettings.objects.count(), 1)

    def test_admin_can_patch_general_settings(self):
        request = self.factory.patch(
            "/api/v1/admin/settings/general/",
            {
                "app_name": "Chesera Pro",
                "support_email": "support@trychesera.com",
                "support_phone": "+15550001111",
                "default_timezone": "America/New_York",
                "date_format": "MM/DD/YYYY",
                "currency": "usd",
            },
            format="json",
        )
        force_authenticate(request, user=self.admin)

        response = AdminGeneralSettingsAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        settings_obj = GeneralSettings.objects.get()
        self.assertEqual(settings_obj.app_name, "Chesera Pro")
        self.assertEqual(settings_obj.currency, "USD")
        self.assertEqual(settings_obj.default_timezone, "America/New_York")

    def test_turning_on_maintenance_mode_notifies_users(self):
        request = self.factory.patch(
            "/api/v1/admin/settings/general/",
            {
                "maintenance_mode": True,
                "maintenance_message": "Chesera is under scheduled maintenance.",
            },
            format="json",
        )
        force_authenticate(request, user=self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = AdminGeneralSettingsAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                notification_type=NotificationType.SYSTEM_ALERT,
                title="Maintenance mode enabled",
            ).exists()
        )
