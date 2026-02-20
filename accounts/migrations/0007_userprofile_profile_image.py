from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_userprofile_hire_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_image",
            field=models.ImageField(blank=True, null=True, upload_to="profile_images/%Y/%m/%d"),
        ),
    ]
