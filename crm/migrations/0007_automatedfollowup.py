from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0034_businesssetting_auto_welcome_message_enabled"),
        ("crm", "0006_contact_lead_contact_link"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomatedFollowUp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive"), ("SUSPENDED", "Suspended")], db_index=True, default="ACTIVE", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence_day", models.PositiveSmallIntegerField()),
                ("scheduled_time", models.DateTimeField(db_index=True)),
                ("follow_up_status", models.CharField(choices=[("scheduled", "Scheduled"), ("sent", "Sent"), ("failed", "Failed"), ("canceled", "Canceled")], db_index=True, default="scheduled", max_length=20)),
                ("requested_channel", models.CharField(blank=True, default="sms", max_length=20)),
                ("resolved_channel", models.CharField(blank=True, default="", max_length=20)),
                ("message_body", models.TextField(blank=True)),
                ("sentdm_message_id", models.CharField(blank=True, db_index=True, default="", max_length=120)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automated_followups", to="crm.lead")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="automated_followups", to="business.organization")),
            ],
            options={
                "db_table": "crm_automated_followups",
                "ordering": ["scheduled_time"],
                "indexes": [
                    models.Index(fields=["organization", "follow_up_status"], name="crm_automat_organiz_0e2b7b_idx"),
                    models.Index(fields=["scheduled_time", "follow_up_status"], name="crm_automat_schedul_81e616_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("lead", "sequence_day"), name="unique_automated_followup_day_per_lead"),
                ],
            },
        ),
    ]
