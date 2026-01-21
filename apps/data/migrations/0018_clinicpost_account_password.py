from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0017_clinicpost_account_memo"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinicpost",
            name="account_password",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
