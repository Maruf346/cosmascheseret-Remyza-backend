from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_city_user_country"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="timezone",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
