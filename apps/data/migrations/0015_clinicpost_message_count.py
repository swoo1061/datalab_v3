from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data", "0014_clinicpost_review_subtype"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinicpost",
            name="message_count",
            field=models.IntegerField(default=0),
        ),
    ]
