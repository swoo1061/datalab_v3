from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0018_clinicpost_account_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinicpost",
            name="doctor_name",
            field=models.CharField(blank=True, default="", max_length=50, verbose_name="담당 원장명"),
        ),
    ]
