from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("welcome", "Welcome"),
                    ("new_user", "New User"),
                    ("subscription_created", "Subscription Created"),
                    ("subscription_active", "Subscription Active"),
                    ("sentdm_profile_requested", "Sent.dm Profile Requested"),
                    ("sentdm_profile_completed", "Sent.dm Profile Completed"),
                    ("sentdm_campaign_requested", "Sent.dm Campaign Requested"),
                    ("whatsapp_connection_requested", "WhatsApp Connection Requested"),
                    ("new_lead", "New Lead"),
                    ("message_received", "Message Received"),
                    ("follow_up_scheduled", "Follow-up Scheduled"),
                    ("follow_up_sent", "Follow-up Sent"),
                    ("follow_up_failed", "Follow-up Failed"),
                    ("system_alert", "System Alert"),
                ],
                max_length=50,
            ),
        ),
    ]
