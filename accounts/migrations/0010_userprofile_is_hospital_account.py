from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_userprofile_force_password_change"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="is_hospital_account",
            field=models.BooleanField(default=False),
        ),
    ]
