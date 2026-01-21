from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0016_clinicpostphoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinicpost",
            name="account",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="clinicpost",
            name="memo",
            field=models.TextField(blank=True, default=""),
        ),
    ]
