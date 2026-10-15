from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.choices import UserType
from accounts.models import User
from common.choices import Status
from crm.choices import LeadStage
from crm.models import Lead
from business.models import Organization
from sentdm.choices import SentDMMessageDirection
from sentdm.models import SentDMMessage
from .models import UserSubscription
from .serializers import UserSubscriptionSerializer
from .services.purchase import SubscriptionValidationService
from .views import (
    AdminMonthlyRevenueAPIView,
    AdminRevenueAnalyticsAPIView,
    AdminSubscriberDetailAPIView,
    AdminSubscriberListAPIView,
    AdminUserAnalyticsAPIView,
    UserSubscriptionViewSet,
)


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
class UserSubscriptionViewSetTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client_user = User.objects.create(phone_number="+15550000003", email="client@example.com")
        self.other_user = User.objects.create(phone_number="+15550000004", email="other@example.com")
        self.admin_user = User.objects.create(
            phone_number="+15550000005",
            email="admin@example.com",
            user_type=UserType.ADMIN,
            is_staff=True,
        )
        UserSubscription.objects.create(
            user=self.client_user,
            product_id="chesera.monthly",
            medium="google",
            purchase_token="client-token",
            start_date=timezone.now(),
        )
        UserSubscription.objects.create(
            user=self.other_user,
            product_id="chesera.yearly",
            medium="apple",
            transaction_id="other-txn",
            start_date=timezone.now(),
        )

    def test_client_list_returns_only_own_subscriptions(self):
        request = self.factory.get("/api/v1/user-subscription/")
        force_authenticate(request, user=self.client_user)

        response = UserSubscriptionViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user"], self.client_user.id)

    def test_admin_list_returns_all_subscriptions(self):
        request = self.factory.get("/api/v1/user-subscription/")
        force_authenticate(request, user=self.admin_user)

        response = UserSubscriptionViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_create_subscription_payment_record(self):
        request = self.factory.post(
            "/api/v1/user-subscription/",
            {
                "medium": "google",
                "product_id": "chesera.monthly",
                "purchase_token": "new-token",
                "is_subscription_active": True,
                "expiry_date": (timezone.now() + timedelta(days=30)).isoformat(),
            },
            format="json",
        )
        force_authenticate(request, user=self.client_user)

        response = UserSubscriptionViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"], self.client_user.id)
        self.assertTrue(response.data["is_active"])


class AdminSubscriptionAnalyticsAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create(
            phone_number="+15550000100",
            email="subscription-admin@example.com",
            user_type=UserType.ADMIN,
            is_staff=True,
        )
        self.active_user = User.objects.create(
            phone_number="+15550000101",
            email="active-subscriber@example.com",
            full_name="Active Subscriber",
        )
        self.trial_user = User.objects.create(
            phone_number="+15550000102",
            email="trial-subscriber@example.com",
            full_name="Trial Subscriber",
        )
        self.suspended_user = User.objects.create(
            phone_number="+15550000103",
            email="suspended@example.com",
            full_name="Suspended User",
            status=Status.INACTIVE,
        )
        now = timezone.now()
        self.active_subscription = UserSubscription.objects.create(
            user=self.active_user,
            product_id="chesera.pro.monthly",
            plan_type="pro",
            medium="apple",
            transaction_id="txn-active-admin-analytics",
            is_subscription_active=True,
            purchase_date=now,
            expiry_date=now + timedelta(days=30),
            expires_at=now + timedelta(days=30),
            amount="79.00",
            currency_code="USD",
        )
        UserSubscription.objects.create(
            user=self.active_user,
            product_id="chesera.pro.monthly.previous",
            plan_type="pro",
            medium="apple",
            transaction_id="txn-previous-admin-analytics",
            is_subscription_active=False,
            purchase_date=now - timedelta(days=35),
            expiry_date=now - timedelta(days=5),
            expires_at=now - timedelta(days=5),
            amount="79.00",
            currency_code="USD",
        )
        UserSubscription.objects.create(
            user=self.trial_user,
            product_id="chesera.trial",
            plan_type="trial",
            medium="google",
            purchase_token="trial-token-admin-analytics",
            status="trial",
            is_subscription_active=False,
            purchase_date=now,
            expiry_date=now + timedelta(days=14),
        )
        organization = Organization.objects.create(owner=self.active_user, name="Analytics Realty")
        Lead.objects.create(organization=organization, contact_number="+15556667777")

    def test_admin_subscriber_list_returns_summary_and_paginated_subscribers(self):
        request = self.factory.get("/api/v1/admin/subscriptions/?page_size=10")
        force_authenticate(request, user=self.admin)

        response = AdminSubscriberListAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["summary"]["total_revenue"]["value"], 158)
        self.assertEqual(response.data["data"]["summary"]["active_subscribers"]["value"], 1)
        self.assertEqual(response.data["data"]["summary"]["trial_users"]["value"], 1)
        self.assertEqual(response.data["data"]["summary"]["suspended_users"]["value"], 1)
        self.assertEqual(response.data["data"]["count"], 3)
        rows_by_user = {row["user_id"]: row for row in response.data["data"]["results"]}
        self.assertEqual(rows_by_user[self.active_user.id]["plan"], "pro")
        self.assertEqual(rows_by_user[self.active_user.id]["billing"], "$79.00/month")
        self.assertEqual(rows_by_user[self.trial_user.id]["plan"], "trial")
        self.assertFalse(rows_by_user[self.suspended_user.id]["is_active"])

    def test_admin_subscriber_detail_returns_lifetime_spent_and_next_billing(self):
        request = self.factory.get(f"/api/v1/admin/subscriptions/{self.active_user.id}/")
        force_authenticate(request, user=self.admin)

        response = AdminSubscriberDetailAPIView.as_view()(request, user_id=self.active_user.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["user_id"], self.active_user.id)
        self.assertEqual(response.data["data"]["lifetime_spent"], 158)
        self.assertIsNotNone(response.data["data"]["next_billing_cycle"])

    def test_admin_monthly_revenue_returns_last_six_months(self):
        request = self.factory.get("/api/v1/admin/revenue/monthly/")
        force_authenticate(request, user=self.admin)

        response = AdminMonthlyRevenueAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 6)
        self.assertIn("month", response.data["data"][0])
        self.assertIn("revenue", response.data["data"][0])

    def test_admin_user_analytics_returns_summary_and_yearly_ratio(self):
        request = self.factory.get("/api/v1/admin/users/analytics/?year=this_year")
        force_authenticate(request, user=self.admin)

        response = AdminUserAnalyticsAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["summary"]["total_users"], 3)
        self.assertEqual(response.data["data"]["summary"]["active_subscriptions"], 1)
        self.assertEqual(response.data["data"]["summary"]["monthly_revenue"], 79)
        self.assertEqual(response.data["data"]["summary"]["total_leads_captured"], 1)
        self.assertEqual(len(response.data["data"]["user_ratio"]), 12)

    def test_admin_revenue_analytics_returns_filtered_summary_and_breakdowns(self):
        organization = self.active_user.organization
        lead = Lead.objects.create(organization=organization, contact_number="+15556667778", stage=LeadStage.HOT)
        Lead.objects.create(organization=organization, contact_number="+15556667779", stage=LeadStage.CONVERTED)
        SentDMMessage.objects.create(
            organization=organization,
            lead=lead,
            direction=SentDMMessageDirection.OUTBOUND,
            to_number="+15556667778",
            body="Hello",
        )
        request = self.factory.get("/api/v1/admin/revenue/analytics/?period=this_month")
        force_authenticate(request, user=self.admin)

        response = AdminRevenueAnalyticsAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["period"], "this_month")
        self.assertEqual(response.data["data"]["summary"]["revenue"]["value"], 79)
        self.assertEqual(response.data["data"]["summary"]["messages_sent"]["value"], 1)
        self.assertGreater(response.data["data"]["summary"]["lead_conversion_percent"]["value"], 0)
        self.assertTrue(response.data["data"]["message_volume_analytics"])
        subscriber_labels = {item["label"] for item in response.data["data"]["subscribers"]}
        self.assertIn("total_subscribers", subscriber_labels)
        self.assertIn("pro_subscribers", subscriber_labels)
        self.assertIn("trial_or_free_users", subscriber_labels)
        lead_labels = {item["label"] for item in response.data["data"]["leads"]}
        self.assertIn("hot_leads", lead_labels)
        self.assertIn("warm_leads", lead_labels)
        self.assertIn("cold_leads", lead_labels)
        self.assertIn("total_leads", lead_labels)

    def test_admin_revenue_analytics_custom_range_requires_dates(self):
        request = self.factory.get("/api/v1/admin/revenue/analytics/?period=custom")
        force_authenticate(request, user=self.admin)

        response = AdminRevenueAnalyticsAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("from_date", response.data["detail"])
