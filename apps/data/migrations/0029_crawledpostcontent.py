from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0028_generatedreview_persona_text"),
    ]

    operations = [
        migrations.CreateModel(
            name="CrawledPostContent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField(max_length=1000)),
                ("platform", models.CharField(db_index=True, default="", max_length=30)),
                ("title", models.CharField(blank=True, default="", max_length=500)),
                ("content", models.TextField(blank=True, default="")),
                ("views", models.IntegerField(blank=True, null=True)),
                ("comments", models.IntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("success", "성공"), ("skipped", "스킵"), ("failed", "실패")], db_index=True, default="success", max_length=20)),
                ("error_message", models.TextField(blank=True, default="")),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
                ("content_length", models.IntegerField(default=0)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crawled_contents", to="data.clinicpost")),
            ],
            options={
                "ordering": ["-fetched_at"],
            },
        ),
        migrations.AddIndex(
            model_name="crawledpostcontent",
            index=models.Index(fields=["platform", "-fetched_at"], name="data_crawl_platform_3a1e3a_idx"),
        ),
    ]

