from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0034_businesssetting_auto_welcome_message_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="sentdm_tax_id_type",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_ein_issuing_country",
            field=models.CharField(blank=True, default="US", max_length=2),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_entity_type",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_brand_street",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_brand_city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_brand_state",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_brand_postal_code",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_opt_in_method",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_opt_in_starting_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_opt_in_form_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_opt_in_screenshot_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_opt_in_checkbox_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_sms_disclaimer_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_privacy_policy_no_mobile_sharing",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_sms_consent_optional",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_sms_checkbox_not_prefilled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_marketing_messages_disclosed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="organization",
            name="sentdm_donation_solicitation_disclosed",
            field=models.BooleanField(default=False),
        ),
    ]
