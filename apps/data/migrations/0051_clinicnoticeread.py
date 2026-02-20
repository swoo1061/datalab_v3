from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0050_clinicnotice"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClinicNoticeRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now=True)),
                ("notice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="data.clinicnotice")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="clinic_notice_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "병원 공지 읽음",
                "verbose_name_plural": "병원 공지 읽음",
                "unique_together": {("notice", "user")},
            },
        ),
        migrations.AddIndex(
            model_name="clinicnoticeread",
            index=models.Index(fields=["user", "notice"], name="data_cnr_user_notice_idx"),
        ),
        migrations.AddIndex(
            model_name="clinicnoticeread",
            index=models.Index(fields=["notice", "user"], name="data_cnr_notice_user_idx"),
        ),
    ]
