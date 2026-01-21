from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0022_calendarmemo_platform"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarmemo",
            name="account",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="calendarmemo",
            name="account_password",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
