from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0049_clinicmessagelog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClinicNotice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("content", models.TextField(blank=True, default="")),
                ("is_pinned", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("clinic", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notices", to="data.clinicguide")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="clinic_notices", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "병원 공지사항",
                "verbose_name_plural": "병원 공지사항",
                "ordering": ["-is_pinned", "-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="clinicnotice",
            index=models.Index(fields=["clinic", "-updated_at"], name="data_cn_clinic_upd_idx"),
        ),
        migrations.AddIndex(
            model_name="clinicnotice",
            index=models.Index(fields=["clinic", "-is_pinned", "-updated_at"], name="data_cn_pin_upd_idx"),
        ),
    ]
