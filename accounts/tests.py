from django.test import TestCase

# Create your tests here.

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.choices import OTPPurpose
from accounts.models import OTPVerification, User
from accounts.views import ClientSignupAPIView, ClientVerifyOTPAPIView, CurrentUserAPIView, CurrentUserCheseraNumberAPIView, CurrentUserPlanAndProgressAPIView
from business.models import Organization
from subscription.models import UserSubscription
from sentdm.choices import SentDMCampaignStatus, SentDMProfileStatus, SentDMWhatsAppConnectionSource, SentDMWhatsAppConnectionStatus
from sentdm.models import SentDMCampaign, SentDMProfile



class ClientSignupAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.payload = {
            "full_name": "Test Agent",
            "email": "agent@example.com",
            "phone_number": "+15558880000",
            "city": "Austin",
            "country": "United States",
            "country_code": "+1",
        }

    def test_signup_creates_unverified_user_and_registration_otp(self):
        request = self.factory.post("/api/v1/client/auth/signup/", self.payload, format="json")

        response = ClientSignupAPIView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(phone_number=self.payload["phone_number"])
        self.assertEqual(user.full_name, "Test Agent")
        self.assertEqual(user.email, "agent@example.com")
        self.assertEqual(user.city, "Austin")
        self.assertEqual(user.country, "United States")
        self.assertEqual(user.country_code, "+1")
        self.assertFalse(user.is_phone_verified)
        self.assertTrue(
            OTPVerification.objects.filter(
                user=user,
                phone_number=self.payload["phone_number"],
                purpose=OTPPurpose.REGISTER,
                is_used=False,
            ).exists()
        )
        self.assertEqual(response.data["data"]["user"]["city"], "Austin")
        self.assertEqual(response.data["data"]["user"]["country"], "United States")

    def test_signup_updates_existing_unverified_user_and_resends_otp(self):
        user = User.objects.create(
            phone_number=self.payload["phone_number"],
            full_name="Old Name",
            email="old@example.com",
            is_phone_verified=False,
        )
        request = self.factory.post("/api/v1/client/auth/signup/", self.payload, format="json")

        response = ClientSignupAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.full_name, "Test Agent")
        self.assertEqual(user.email, "agent@example.com")
        self.assertEqual(user.city, "Austin")
        self.assertEqual(response.data["data"]["is_new_user"], False)
        self.assertEqual(OTPVerification.objects.filter(user=user, purpose=OTPPurpose.REGISTER, is_used=False).count(), 1)

    def test_signup_rejects_verified_phone_number(self):
        User.objects.create(
            phone_number=self.payload["phone_number"],
            email="verified@example.com",
            is_phone_verified=True,
        )
        request = self.factory.post("/api/v1/client/auth/signup/", self.payload, format="json")

        response = ClientSignupAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.data)

    def test_signup_otp_verify_returns_new_profile_fields(self):
        signup_request = self.factory.post("/api/v1/client/auth/signup/", self.payload, format="json")
        ClientSignupAPIView.as_view()(signup_request)
        otp = OTPVerification.objects.get(phone_number=self.payload["phone_number"], purpose=OTPPurpose.REGISTER)
        verify_request = self.factory.post(
            "/api/v1/client/auth/verify-otp/",
            {"phone_number": self.payload["phone_number"], "otp": otp.otp_code},
            format="json",
        )

        response = ClientVerifyOTPAPIView.as_view()(verify_request)

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(phone_number=self.payload["phone_number"])
        self.assertTrue(user.is_phone_verified)
        self.assertEqual(response.data["data"]["user"]["email"], "agent@example.com")
        self.assertEqual(response.data["data"]["user"]["city"], "Austin")
        self.assertEqual(response.data["data"]["user"]["country"], "United States")
        self.assertEqual(response.data["data"]["user"]["country_code"], "+1")

class CurrentUserAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create(
            phone_number="+15551112222",
            email="original@example.com",
            full_name="Original Name",
            city="Austin",
            country="United States",
            country_code="+1",
            is_phone_verified=True,
        )

    def test_patch_keeps_identity_and_system_fields_read_only(self):
        original_last_activity_at = self.user.last_activity_at
        request = self.factory.patch(
            "/api/v1/me/",
            {
                "phone_number": "+15559999999",
                "user_type": "ADMIN",
                "is_phone_verified": False,
                "last_activity_at": "2026-09-12T03:57:26.545Z",
                "email": "updated@example.com",
                "full_name": "Updated Name",
                "city": "Dallas",
                "country": "United States",
                "country_code": "+1",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = CurrentUserAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "+15551112222")
        self.assertEqual(self.user.user_type, "CLIENT")
        self.assertTrue(self.user.is_phone_verified)
        self.assertEqual(self.user.last_activity_at, original_last_activity_at)
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.full_name, "Updated Name")
        self.assertEqual(self.user.city, "Dallas")
        self.assertEqual(response.data["data"]["phone_number"], "+15551112222")
        self.assertEqual(response.data["data"]["user_type"], "CLIENT")
        self.assertTrue(response.data["data"]["is_phone_verified"])

class CurrentUserCheseraNumberAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create(phone_number="+15556660001", email="number@example.com")
        self.organization = Organization.objects.create(owner=self.user, name="Number Realty")

    def call_endpoint(self):
        request = self.factory.get("/api/v1/me/chesera-number/")
        force_authenticate(request, user=self.user)
        return CurrentUserCheseraNumberAPIView.as_view()(request)

    def test_returns_pending_when_no_chesera_number_is_assigned(self):
        response = self.call_endpoint()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(response.data["data"]["assigned"])
        self.assertIsNone(response.data["data"]["phone_number"])
        self.assertEqual(response.data["data"]["number_assignment_status"], "pending")
        self.assertEqual(response.data["data"]["provider"], "sentdm")
        self.assertFalse(response.data["data"]["sms_rcs_active"])

    def test_returns_assigned_chesera_number_from_sentdm_profile(self):
        SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_number_assigned",
            name="Number Sender",
            status=SentDMProfileStatus.APPROVED,
            phone_number="+15559990000",
        )

        response = self.call_endpoint()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["assigned"])
        self.assertEqual(response.data["data"]["phone_number"], "+15559990000")
        self.assertEqual(response.data["data"]["number_assignment_status"], "assigned")
        self.assertEqual(response.data["data"]["profile_id"], "profile_number_assigned")
        self.assertEqual(response.data["data"]["profile_status"], SentDMProfileStatus.APPROVED)
        self.assertTrue(response.data["data"]["sms_rcs_active"])

class CurrentUserPlanAndProgressAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create(phone_number="+15559990001", email="progress@example.com")
        self.organization = Organization.objects.create(
            owner=self.user,
            name="Progress Realty",
            sentdm_expected_daily_volume=0,
        )

    def complete_sentdm_compliance(self):
        self.organization.sentdm_legal_name = "Progress Realty LLC"
        self.organization.sentdm_tax_id = "12-3456789"
        self.organization.sentdm_vertical = "REAL_ESTATE"
        self.organization.sentdm_authorized_rep_name = "Progress Agent"
        self.organization.sentdm_authorized_rep_title = "Owner"
        self.organization.sentdm_authorized_rep_email = "owner@progressrealty.example"
        self.organization.sentdm_authorized_rep_phone = "+15559990001"
        self.organization.sentdm_support_email = "support@progressrealty.example"
        self.organization.sentdm_support_phone = "+15559990002"
        self.organization.sentdm_privacy_policy_url = "https://progressrealty.example/privacy"
        self.organization.sentdm_terms_url = "https://progressrealty.example/terms"
        self.organization.sentdm_opt_in_url = "https://progressrealty.example/contact"
        self.organization.sentdm_opt_in_description = "Leads submit the website contact form and agree to receive replies about their inquiry."
        self.organization.sentdm_messaging_use_case = "Customer care replies for opted-in real estate leads."
        self.organization.sentdm_messaging_use_case_us = "CUSTOMER_CARE"
        self.organization.sentdm_sample_message_1 = "Hi Alex! This is the assistant for Progress Realty. Thanks for reaching out about your home search. Reply STOP to opt out."
        self.organization.sentdm_sample_message_2 = "Progress Realty: We received your property question and can help with next steps. Reply STOP to opt out."
        self.organization.sentdm_sample_message_3 = "Progress Realty: Thanks for your message about a showing. Reply STOP to opt out."
        self.organization.sentdm_opt_in_confirmation_message = "Progress Realty: Thanks for opting in. Reply STOP to opt out."
        self.organization.sentdm_opt_out_confirmation_message = "Progress Realty: You have been unsubscribed and will no longer receive messages."
        self.organization.sentdm_help_response_message = "Progress Realty: Contact support@progressrealty.example for help. Reply STOP to opt out."
        self.organization.sentdm_expected_daily_volume = 25
        self.organization.save()

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

    def test_free_user_gets_dashboard_only_activation_status(self):
        request = self.factory.get("/api/v1/me/plan-and-progress/")
        force_authenticate(request, user=self.user)

        response = CurrentUserPlanAndProgressAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["data"]["has_active_subscription"])
        self.assertEqual(response.data["data"]["messaging_activation"]["status"], "subscription_required")
        self.assertEqual(
            response.data["data"]["messaging_activation"]["message"],
            "Messaging activates after a paid subscription is active.",
        )
        self.assertFalse(response.data["data"]["messaging_activation"]["sms_rcs"]["active"])
        self.assertEqual(response.data["data"]["whatsapp"]["status"], "not_connected")

    def test_paid_user_with_profile_but_no_number_gets_inventory_delay_message(self):
        UserSubscription.objects.create(
            user=self.user,
            organization=self.organization,
            product_id="chesera.monthly",
            plan_type="monthly",
            medium="apple",
            transaction_id="txn_progress_pending_number",
            is_subscription_active=True,
            start_date=timezone.now(),
            expiry_date=timezone.now() + timedelta(days=30),
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.complete_sentdm_compliance()
        SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_progress_pending_number",
            name="Progress Sender Pending Number",
            status=SentDMProfileStatus.PROCESSING,
            phone_number="",
        )
        request = self.factory.get("/api/v1/me/plan-and-progress/")
        force_authenticate(request, user=self.user)

        response = CurrentUserPlanAndProgressAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["number_assignment_status"], "pending")
        self.assertEqual(response.data["data"]["sentdm_number"]["status"], "pending")
        self.assertEqual(response.data["data"]["sentdm_number"]["number_assignment_status"], "pending")
        self.assertEqual(
            response.data["data"]["sentdm_number"]["message"],
            "Messaging activation is in progress. Number assignment may take additional time if local inventory is unavailable.",
        )
        self.assertEqual(
            response.data["data"]["messaging_activation"]["sms_rcs"]["number_assignment_status"],
            "pending",
        )

    def test_paid_user_with_active_sentdm_sms_and_optional_whatsapp_not_connected(self):
        UserSubscription.objects.create(
            user=self.user,
            organization=self.organization,
            product_id="chesera.monthly",
            plan_type="monthly",
            medium="apple",
            transaction_id="txn_progress_active",
            is_subscription_active=True,
            start_date=timezone.now(),
            expiry_date=timezone.now() + timedelta(days=30),
            expires_at=timezone.now() + timedelta(days=30),
        )
        profile = SentDMProfile.objects.create(
            user=self.user,
            organization=self.organization,
            profile_id="profile_progress_active",
            name="Progress Sender",
            status=SentDMProfileStatus.APPROVED,
            phone_number="+15559990000",
            whatsapp_connection_source=SentDMWhatsAppConnectionSource.INHERITED,
            whatsapp_connection_status=SentDMWhatsAppConnectionStatus.NOT_CONNECTED,
        )
        self.organization.sentdm_legal_name = "Progress Realty LLC"
        self.organization.sentdm_tax_id = "12-3456789"
        self.organization.sentdm_vertical = "REAL_ESTATE"
        self.organization.sentdm_authorized_rep_name = "Progress Agent"
        self.organization.sentdm_authorized_rep_title = "Owner"
        self.organization.sentdm_authorized_rep_email = "owner@progressrealty.example"
        self.organization.sentdm_authorized_rep_phone = "+15559990001"
        self.organization.sentdm_support_email = "support@progressrealty.example"
        self.organization.sentdm_support_phone = "+15559990002"
        self.organization.sentdm_privacy_policy_url = "https://progressrealty.example/privacy"
        self.organization.sentdm_terms_url = "https://progressrealty.example/terms"
        self.organization.sentdm_opt_in_url = "https://progressrealty.example/contact"
        self.organization.sentdm_opt_in_description = "Leads submit the website contact form and agree to receive replies about their inquiry."
        self.organization.sentdm_messaging_use_case = "Customer care replies for opted-in real estate leads."
        self.organization.sentdm_messaging_use_case_us = "CUSTOMER_CARE"
        self.organization.sentdm_sample_message_1 = "Hi Alex! This is the assistant for Progress Realty. Thanks for reaching out about your home search. Reply STOP to opt out."
        self.organization.sentdm_sample_message_2 = "Progress Realty: We received your property question and can help with next steps. Reply STOP to opt out."
        self.organization.sentdm_sample_message_3 = "Progress Realty: Thanks for your message about a showing. Reply STOP to opt out."
        self.organization.sentdm_opt_in_confirmation_message = "Progress Realty: Thanks for opting in. Reply STOP to opt out."
        self.organization.sentdm_opt_out_confirmation_message = "Progress Realty: You have been unsubscribed and will no longer receive messages."
        self.organization.sentdm_help_response_message = "Progress Realty: Contact support@progressrealty.example for help. Reply STOP to opt out."
        self.organization.sentdm_expected_daily_volume = 25
        self.organization.save()
        SentDMCampaign.objects.create(
            profile=profile,
            organization=self.organization,
            campaign_id="campaign_progress_active",
            name="Progress Campaign",
            status=SentDMCampaignStatus.ACTIVE,
            submitted_to_tcr=True,
        )
        request = self.factory.get("/api/v1/me/plan-and-progress/")
        force_authenticate(request, user=self.user)

        response = CurrentUserPlanAndProgressAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["messaging_activation"]["status"], "active")
        self.assertEqual(response.data["data"]["messaging_activation"]["message"], "Messaging active.")
        self.assertEqual(response.data["data"]["number_assignment_status"], "assigned")
        self.assertEqual(response.data["data"]["messaging_activation"]["sms_rcs"]["number_assignment_status"], "assigned")
        self.assertTrue(response.data["data"]["sentdm_number"]["assigned"])
        self.assertEqual(response.data["data"]["sentdm_number"]["phone_number"], "+15559990000")
        self.assertEqual(response.data["data"]["whatsapp"]["source"], "inherited")
        self.assertFalse(response.data["data"]["whatsapp"]["active"])
        self.assertEqual(response.data["data"]["sentdm_profile"]["is_agent_whatsapp_active"], False)
