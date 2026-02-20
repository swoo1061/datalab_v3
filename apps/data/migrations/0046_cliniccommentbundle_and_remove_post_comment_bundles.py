from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("data", "0045_clinicpost_comment_bundles"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClinicCommentBundle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField(max_length=1000)),
                ("image", models.ImageField(upload_to="clinic_comment_bundles/%Y/%m/%d")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comment_bundles",
                        to="data.clinicguide",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="clinic_comment_bundles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="cliniccommentbundle",
            index=models.Index(fields=["clinic", "-created_at"], name="data_clinic_clinic__9cf239_idx"),
        ),
        migrations.RemoveField(
            model_name="clinicpost",
            name="comment_bundles",
        ),
    ]
