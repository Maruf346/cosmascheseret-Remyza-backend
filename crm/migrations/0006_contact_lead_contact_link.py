# Generated manually for separate CRM contacts.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0005_lead_source_stage_contact_workflow"),
    ]

    operations = [
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive"), ("SUSPENDED", "Suspended")], db_index=True, default="ACTIVE", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("full_name", models.CharField(blank=True, max_length=100)),
                ("country_code", models.CharField(blank=True, max_length=10)),
                ("phone_number", models.CharField(max_length=30)),
                ("contact_number", models.CharField(db_index=True, max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("business_name", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("source", models.CharField(choices=[("manual", "Manual"), ("csv_upload", "CSV Upload"), ("auto_capture", "Auto Capture"), ("sentdm", "Sent.dm")], db_index=True, default="manual", max_length=50)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("linked_lead", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="contact_record", to="crm.lead")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contacts", to="business.organization")),
            ],
            options={
                "db_table": "crm_contacts",
                "ordering": ["full_name", "-created_at"],
            },
        ),
        migrations.AddField(
            model_name="lead",
            name="contact",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lead_record", to="crm.contact"),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["organization", "contact_number"], name="crm_contact_organiz_f04d78_idx"),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(fields=["source"], name="crm_contact_source_f89b14_idx"),
        ),
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.UniqueConstraint(fields=("organization", "contact_number"), name="unique_contact_per_organization"),
        ),
    ]