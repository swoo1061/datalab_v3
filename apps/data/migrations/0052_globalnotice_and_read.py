from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0051_clinicnoticeread"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GlobalNotice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("content", models.TextField(blank=True, default="")),
                ("is_pinned", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="global_notices", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "전체 공지사항",
                "verbose_name_plural": "전체 공지사항",
                "ordering": ["-is_pinned", "-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="GlobalNoticeRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now=True)),
                ("notice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="data.globalnotice")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="global_notice_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "전체 공지 읽음",
                "verbose_name_plural": "전체 공지 읽음",
                "unique_together": {("notice", "user")},
            },
        ),
        migrations.AddIndex(
            model_name="globalnotice",
            index=models.Index(fields=["-updated_at"], name="data_gn_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="globalnotice",
            index=models.Index(fields=["-is_pinned", "-updated_at"], name="data_gn_pin_upd_idx"),
        ),
        migrations.AddIndex(
            model_name="globalnoticeread",
            index=models.Index(fields=["user", "notice"], name="data_gnr_user_notice_idx"),
        ),
        migrations.AddIndex(
            model_name="globalnoticeread",
            index=models.Index(fields=["notice", "user"], name="data_gnr_notice_user_idx"),
        ),
    ]
