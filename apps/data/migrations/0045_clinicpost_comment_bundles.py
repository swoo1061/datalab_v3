from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0044_reviewschedulememo"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinicpost",
            name="comment_bundles",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

