from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_remove_a2pcampaign_brand_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneralSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive"), ("SUSPENDED", "Suspended")], db_index=True, default="ACTIVE", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("app_name", models.CharField(default="Chesera", max_length=100)),
                ("support_email", models.EmailField(blank=True, max_length=254)),
                ("support_phone", models.CharField(blank=True, max_length=30)),
                ("default_timezone", models.CharField(default="UTC", max_length=64)),
                ("date_format", models.CharField(default="MM/DD/YYYY", max_length=50)),
                ("currency", models.CharField(default="USD", max_length=10)),
                ("maintenance_mode", models.BooleanField(default=False)),
                ("maintenance_message", models.TextField(blank=True, default="The platform is currently under maintenance. Please check back shortly.")),
                ("app_logo", models.ImageField(blank=True, null=True, upload_to="settings/app_logo/")),
            ],
            options={
                "verbose_name": "General Setting",
                "verbose_name_plural": "General Settings",
            },
        ),
    ]
