from django.test import TestCase

# Create your tests here.

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from accounts.views import CurrentUserPlanAndProgressAPIView
from business.models import Organization
from subscription.models import UserSubscription


class CurrentUserPlanAndProgressAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create(phone_number="+15559990001", email="progress@example.com")
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Progress Realty",
            sentdm_expected_daily_volume=0,
        )

    def test_returns_iap_and_sentdm_progress_without_twilio_requirements(self):
        UserSubscription.objects.create(
            user=self.user,
            organization=self.organization,
            product_id="chesera.monthly",
            plan_type="monthly",
            medium="apple",
            transaction_id="txn_progress",
            is_subscription_active=True,
            start_date=timezone.now(),
            expiry_date=timezone.now() + timedelta(days=30),
            expires_at=timezone.now() + timedelta(days=30),
        )
        request = self.factory.get("/api/v1/me/plan-and-progress/")
        force_authenticate(request, user=self.user)

        response = CurrentUserPlanAndProgressAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["has_active_subscription"])
        self.assertEqual(response.data["data"]["plan_type"], "monthly")
        self.assertEqual(response.data["data"]["organization"]["sentdm_expected_daily_volume"], 0)
        step_titles = [step["title"] for step in response.data["data"]["progress"]["steps"]]
        self.assertIn("Sent.dm Sender Profile Created", step_titles)
        self.assertIn("10DLC Campaign Submitted", step_titles)