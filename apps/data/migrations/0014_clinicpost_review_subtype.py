from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data", "0013_clinicassignee"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinicpost",
            name="review_subtype",
            field=models.CharField(
                blank=True,
                choices=[("text", "텍스트 후기"), ("photo", "사진 후기")],
                db_index=True,
                max_length=20,
                null=True,
            ),
        ),
    ]
