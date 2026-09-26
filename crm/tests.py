from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from business.models import BusinessSetting, Organization
from communications.choices import ConversationStatus, MessageDirection, MessageStatus
from communications.models import Conversation, Message
from crm.choices import LeadActivityType, LeadSource, LeadStage
from crm.models import Contact, Lead, LeadActivity


class CRMContactAndLeadAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number="+15550000001",
            password="pass12345",
            email="owner@example.com",
        )
        self.organization = Organization.objects.create(owner=self.user, name="Chesera Test", email="owner@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def response_items(self, response):
        data = response.json()
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def test_manual_contact_create_does_not_create_lead(self):
        response = self.client.post(
            "/api/v1/contacts/",
            {
                "full_name": "Jane Smith",
                "country_code": "+1",
                "phone_number": "5551112222",
                "email": "jane@example.com",
                "business_name": "Jane Homes",
                "notes": "Met at open house.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        contact = Contact.objects.get(contact_number="+15551112222")
        self.assertEqual(contact.organization, self.organization)
        self.assertEqual(contact.business_name, "Jane Homes")
        self.assertEqual(contact.source, LeadSource.MANUAL)
        self.assertFalse(Lead.objects.filter(contact_number="+15551112222").exists())
        self.assertFalse(response.json()["is_lead"])
    def test_manual_contact_create_does_not_queue_welcome_even_when_setting_enabled(self):
        BusinessSetting.objects.create(
            user=self.user,
            organization=self.organization,
            auto_welcome_message_enabled=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/contacts/",
                {
                    "full_name": "Welcome Contact",
                    "country_code": "+1",
                    "phone_number": "5557778888",
                    "email": "welcome-contact@example.com",
                    "business_name": "Welcome Co",
                    "notes": "Do not auto-send welcome.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.content)
        contact = Contact.objects.get(contact_number="+15557778888")
        self.assertNotIn("welcome_message", contact.metadata or {})

    def test_csv_upload_creates_contacts_and_returns_duplicates(self):
        Contact.objects.create(
            organization=self.organization,
            full_name="Existing Contact",
            country_code="+1",
            phone_number="5553334444",
            contact_number="+15553334444",
            source=LeadSource.MANUAL,
        )
        csv_content = (
            "full_name,country_code,phone_number,email,business_name,notes\n"
            "New Contact,+1,5552223333,new@example.com,New Co,Fresh contact\n"
            "Duplicate Existing,+1,5553334444,dup@example.com,Dup Co,Already saved\n"
            "Duplicate In File,+1,5552223333,dup2@example.com,Dup File,Repeated\n"
            "Missing Phone,+1,,bad@example.com,Bad Co,No phone\n"
        )
        upload = SimpleUploadedFile("contacts.csv", csv_content.encode("utf-8"), content_type="text/csv")

        response = self.client.post("/api/v1/contacts/upload-csv/", {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["created_count"], 1)
        self.assertEqual(data["duplicate_count"], 2)
        self.assertEqual(data["error_count"], 1)
        self.assertEqual(Contact.objects.get(contact_number="+15552223333").source, LeadSource.CSV_UPLOAD)
        self.assertFalse(Lead.objects.filter(contact_number="+15552223333").exists())
        self.assertEqual({item["contact_number"] for item in data["duplicates"]}, {"+15553334444", "+15552223333"})

    def test_lead_list_is_paginated_and_stage_filter_groups_hot_warm_cold(self):
        Lead.objects.create(organization=self.organization, contact_number="+15550000002", stage=LeadStage.HOT)
        Lead.objects.create(organization=self.organization, contact_number="+15550000003", stage=LeadStage.WARM)
        Lead.objects.create(organization=self.organization, contact_number="+15550000004", stage=LeadStage.QUALIFIED)
        Lead.objects.create(organization=self.organization, contact_number="+15550000005", stage=LeadStage.COLD)
        Lead.objects.create(organization=self.organization, contact_number="+15550000006", stage=LeadStage.NEW)

        stats_response = self.client.get("/api/v1/leads/stats/")
        self.assertEqual(stats_response.status_code, 200, stats_response.content)
        self.assertEqual(stats_response.json()["hot"], 1)
        self.assertEqual(stats_response.json()["warm"], 2)
        self.assertEqual(stats_response.json()["cold"], 2)

        warm_response = self.client.get("/api/v1/leads/?stage=warm&page_size=1")
        self.assertEqual(warm_response.status_code, 200, warm_response.content)
        data = warm_response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["hot_count"], 1)
        self.assertEqual(data["warm_count"], 2)
        self.assertEqual(data["cold_count"], 2)
        self.assertEqual(len(data["results"]), 1)
        self.assertIn("next", data)

    def test_lead_detail_includes_conversation_metrics_and_activities(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Conversation Contact",
            country_code="+1",
            phone_number="5554445555",
            contact_number="+15554445555",
            source=LeadSource.AUTO_CAPTURE,
        )
        lead = Lead.objects.create(
            organization=self.organization,
            contact=contact,
            full_name="Conversation Lead",
            contact_number="+15554445555",
            source=LeadSource.AUTO_CAPTURE,
            score=75,
        )
        contact.linked_lead = lead
        contact.save(update_fields=["linked_lead", "updated_at"])
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivityType.CREATED,
            title="Lead created",
            description="Auto captured.",
        )
        conversation = Conversation.objects.create(
            organization=self.organization,
            lead=lead,
            status=ConversationStatus.ACTIVE,
        )
        Message.objects.create(
            lead=lead,
            conversation=conversation,
            direction=MessageDirection.INBOUND,
            sender="+15554445555",
            recipient="+15550000001",
            content="Hello",
            provider_message_sid="msg-in-1",
            status=MessageStatus.DELIVERED,
        )
        Message.objects.create(
            lead=lead,
            conversation=conversation,
            direction=MessageDirection.OUTBOUND,
            sender="+15550000001",
            recipient="+15554445555",
            content="Hi there",
            provider_message_sid="msg-out-1",
            status=MessageStatus.SENT,
            is_ai_generated=True,
        )

        response = self.client.get(f"/api/v1/leads/{lead.id}/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["contact"], contact.id)
        self.assertEqual(data["score_percentage"], 75)
        self.assertEqual(data["total_messages"], 2)
        self.assertEqual(data["response_rate"], 100)
        self.assertEqual(len(data["conversation"]), 2)
        self.assertEqual(data["activities"][0]["title"], "Lead created")

    def test_lead_conversation_endpoint_returns_paginated_messages(self):
        lead = Lead.objects.create(
            organization=self.organization,
            full_name="Conversation API Lead",
            contact_number="+15556667777",
            source=LeadSource.AUTO_CAPTURE,
        )
        conversation = Conversation.objects.create(
            organization=self.organization,
            lead=lead,
            status=ConversationStatus.ACTIVE,
            unread_messages=2,
        )
        for index in range(3):
            Message.objects.create(
                lead=lead,
                conversation=conversation,
                direction=MessageDirection.INBOUND if index == 0 else MessageDirection.OUTBOUND,
                sender="+15556667777" if index == 0 else "+15550000001",
                recipient="+15550000001" if index == 0 else "+15556667777",
                content=f"Message {index + 1}",
                provider_message_sid=f"conversation-api-{index + 1}",
                status=MessageStatus.DELIVERED,
            )

        response = self.client.get(f"/api/v1/leads/{lead.id}/conversation/?page_size=2")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["content"], "Message 1")
        self.assertEqual(data["results"][0]["conversation"], conversation.id)
        self.assertIn("next", data)

    def test_lead_inbox_returns_one_row_per_lead_with_latest_message(self):
        lead_one = Lead.objects.create(
            organization=self.organization,
            full_name="Inbox Lead One",
            contact_number="+15558880001",
            source=LeadSource.AUTO_CAPTURE,
            stage=LeadStage.HOT,
        )
        lead_two = Lead.objects.create(
            organization=self.organization,
            full_name="Inbox Lead Two",
            contact_number="+15558880002",
            source=LeadSource.AUTO_CAPTURE,
            stage=LeadStage.WARM,
        )
        Lead.objects.create(
            organization=self.organization,
            full_name="No Messages Lead",
            contact_number="+15558880003",
            source=LeadSource.MANUAL,
        )
        conversation_one = Conversation.objects.create(
            organization=self.organization,
            lead=lead_one,
            status=ConversationStatus.ACTIVE,
            unread_messages=1,
        )
        conversation_two = Conversation.objects.create(
            organization=self.organization,
            lead=lead_two,
            status=ConversationStatus.ACTIVE,
        )
        Message.objects.create(
            lead=lead_one,
            conversation=conversation_one,
            direction=MessageDirection.INBOUND,
            sender="+15558880001",
            recipient="+15550000001",
            content="First inbox message",
            provider_message_sid="inbox-one-first",
            status=MessageStatus.DELIVERED,
        )
        Message.objects.create(
            lead=lead_one,
            conversation=conversation_one,
            direction=MessageDirection.OUTBOUND,
            sender="+15550000001",
            recipient="+15558880001",
            content="Latest inbox message",
            provider_message_sid="inbox-one-latest",
            status=MessageStatus.SENT,
        )
        Message.objects.create(
            lead=lead_two,
            conversation=conversation_two,
            direction=MessageDirection.INBOUND,
            sender="+15558880002",
            recipient="+15550000001",
            content="Only lead two message",
            provider_message_sid="inbox-two-only",
            status=MessageStatus.DELIVERED,
        )

        response = self.client.get("/api/v1/leads/inbox/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["count"], 2)
        results_by_id = {item["id"]: item for item in data["results"]}
        self.assertEqual(set(results_by_id), {lead_one.id, lead_two.id})
        self.assertEqual(results_by_id[lead_one.id]["last_message"]["content"], "Latest inbox message")
        self.assertEqual(results_by_id[lead_one.id]["unread_messages"], 1)
        self.assertEqual(results_by_id[lead_one.id]["total_messages"], 2)
        self.assertEqual(results_by_id[lead_two.id]["last_message"]["content"], "Only lead two message")
