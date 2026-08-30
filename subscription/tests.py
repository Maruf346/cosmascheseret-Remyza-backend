from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.models import User
from .models import UserSubscription
from .serializers import UserSubscriptionSerializer
from .services.purchase import SubscriptionValidationService


class SubscriptionIAPSerializerTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create(phone_number="+15550000001", email="user@example.com")
        self.request = self.factory.post("/api/v1/user-subscription/")
        self.request.user = self.user

    def test_google_purchase_requires_purchase_token(self):
        serializer = UserSubscriptionSerializer(
            data={"medium": "google", "product_id": "chesera.monthly"},
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purchase_token", serializer.errors)

    def test_apple_purchase_requires_transaction_identifier(self):
        serializer = UserSubscriptionSerializer(
            data={"medium": "apple", "product_id": "chesera.monthly"},
            context={"request": self.request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("transaction_id", serializer.errors)

    def test_create_assigns_request_user_and_sets_legacy_status(self):
        expiry = timezone.now() + timedelta(days=30)
        serializer = UserSubscriptionSerializer(
            data={
                "medium": "google",
                "product_id": "chesera.monthly",
                "purchase_token": "purchase-token",
                "is_subscription_active": True,
                "expiry_date": expiry.isoformat(),
            },
            context={"request": self.request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        subscription = serializer.save()

        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.status, "active")
        self.assertEqual(subscription.expires_at, subscription.expiry_date)


class SubscriptionValidationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone_number="+15550000002", email="paid@example.com")

    def test_active_iap_subscription_is_current_subscription(self):
        subscription = UserSubscription.objects.create(
            user=self.user,
            product_id="chesera.monthly",
            medium="apple",
            transaction_id="txn_123",
            is_subscription_active=True,
            start_date=timezone.now(),
            expiry_date=timezone.now() + timedelta(days=30),
            expires_at=timezone.now() + timedelta(days=30),
        )

        self.assertEqual(SubscriptionValidationService.get_current_subscription(self.user), subscription)
        self.assertTrue(SubscriptionValidationService.has_active_subscription(self.user))

    def test_expired_iap_subscription_is_not_active(self):
        UserSubscription.objects.create(
            user=self.user,
            product_id="chesera.monthly",
            medium="apple",
            transaction_id="txn_expired",
            is_subscription_active=True,
            start_date=timezone.now() - timedelta(days=60),
            expiry_date=timezone.now() - timedelta(days=1),
            expires_at=timezone.now() - timedelta(days=1),
        )

        self.assertIsNone(SubscriptionValidationService.get_current_subscription(self.user))
        self.assertFalse(SubscriptionValidationService.has_active_subscription(self.user))