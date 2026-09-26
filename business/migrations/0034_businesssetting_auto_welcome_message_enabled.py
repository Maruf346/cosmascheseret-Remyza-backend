# Generated manually for contact welcome message setting.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0033_organization_sentdm_whatsapp_access_token_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="businesssetting",
            name="auto_welcome_message_enabled",
            field=models.BooleanField(default=False),
        ),
    ]