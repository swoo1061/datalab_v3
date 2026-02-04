from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("data", "0033_internalmessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="InternalMessageAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="internal_messages/%Y/%m/%d")),
                ("original_name", models.CharField(blank=True, default="", max_length=255)),
                ("content_type", models.CharField(blank=True, default="", max_length=120)),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="data.internalmessage",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
