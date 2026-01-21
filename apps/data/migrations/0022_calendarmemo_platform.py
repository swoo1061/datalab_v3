from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0021_calendar_memo"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarmemo",
            name="platform",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
    ]
