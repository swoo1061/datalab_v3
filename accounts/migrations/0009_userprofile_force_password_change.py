from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_userprofile_presence_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="force_password_change",
            field=models.BooleanField(default=False),
        ),
    ]
