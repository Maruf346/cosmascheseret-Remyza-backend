from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.choices import UserType
from accounts.models import User
from .models import Notification, NotificationPriority, NotificationType
from .services import NotificationService


class NotificationServiceTests(TestCase):
    def test_normal_user_notification_is_rest_only(self):
        user = User.objects.create_user(phone_number="+15550001001", email="user@example.com")

        with patch("notifications.services.NotificationService._send_websocket") as mocked_ws:
            notification = NotificationService.create_notification(
                user=user,
                notification_type=NotificationType.SYSTEM_ALERT,
                title="REST only",
                body="Normal users read notifications through the REST API.",
            )

        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.filter(user=user).count(), 1)
        mocked_ws.assert_not_called()

    def test_admin_notification_is_saved_and_pushed_to_websocket(self):
        admin = User.objects.create_user(
            phone_number="+15550001002",
            email="admin@example.com",
            user_type=UserType.ADMIN,
            is_staff=True,
        )

        with patch("notifications.services.NotificationService._send_websocket") as mocked_ws:
            with self.captureOnCommitCallbacks(execute=True):
                notification = NotificationService.create_notification(
                    user=admin,
                    notification_type=NotificationType.NEW_USER,
                    title="Admin push",
                    body="Admins receive REST and websocket notifications.",
                    priority=NotificationPriority.HIGH,
                )

        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.filter(user=admin).count(), 1)
        mocked_ws.assert_called_once_with(notification)


class NotificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+15550002001", email="api@example.com")
        self.other_user = User.objects.create_user(phone_number="+15550002002", email="other@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_returns_only_authenticated_users_notifications(self):
        own = Notification.objects.create(
            user=self.user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Own notification",
            body="Visible",
        )
        Notification.objects.create(
            user=self.other_user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Other notification",
            body="Hidden",
        )

        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], str(own.id))

    def test_mark_read_and_unread_count(self):
        notification = Notification.objects.create(
            user=self.user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Unread",
            body="Needs read state.",
        )

        unread_response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(unread_response.status_code, 200, unread_response.content)
        self.assertEqual(unread_response.json()["unread_count"], 1)

        mark_response = self.client.post(f"/api/v1/notifications/{notification.id}/mark-read/")
        self.assertEqual(mark_response.status_code, 200, mark_response.content)
        self.assertTrue(mark_response.json()["is_read"])

        unread_response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(unread_response.json()["unread_count"], 0)

    def test_clear_read_deletes_only_read_notifications(self):
        Notification.objects.create(
            user=self.user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Read",
            body="Delete me.",
            is_read=True,
        )
        unread = Notification.objects.create(
            user=self.user,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Unread",
            body="Keep me.",
        )

        response = self.client.delete("/api/v1/notifications/clear-read/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["deleted_count"], 1)
        self.assertEqual(list(Notification.objects.filter(user=self.user)), [unread])