# Generated manually for CRM lead stage/source workflow.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0033_organization_sentdm_whatsapp_access_token_and_more"),
        ("crm", "0004_lead_is_opted_out_lead_opt_out_keyword_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="business_phone",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="leads", to="business.phonenumber"),
        ),
        migrations.AddField(
            model_name="lead",
            name="source",
            field=models.CharField(choices=[("manual", "Manual"), ("csv_upload", "CSV Upload"), ("auto_capture", "Auto Capture"), ("sentdm", "Sent.dm")], db_index=True, default="auto_capture", max_length=50),
        ),
        migrations.AlterField(
            model_name="lead",
            name="stage",
            field=models.CharField(choices=[("cold", "Cold"), ("warm", "Warm"), ("hot", "Hot"), ("new", "New"), ("contacted", "Contacted"), ("qualified", "Qualified"), ("converted", "Converted"), ("lost", "Lost")], db_index=True, default="cold", max_length=20),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(fields=["source"], name="crm_leads_source_cd391c_idx"),
        ),
    ]