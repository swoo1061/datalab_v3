from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_userprofile_profile_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="presence_status",
            field=models.CharField(
                choices=[
                    ("online", "접속중"),
                    ("away", "자리비움"),
                    ("meeting", "미팅중"),
                    ("dnd", "방해금지"),
                    ("offline", "오프라인"),
                ],
                default="offline",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="presence_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
