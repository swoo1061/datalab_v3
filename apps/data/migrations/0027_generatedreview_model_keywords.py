from django.db import migrations, models
from django.db.models import JSONField


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0026_clinicpost_opinion_subtype"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedreview",
            name="model_used",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="사용한 모델"),
        ),
        migrations.AddField(
            model_name="generatedreview",
            name="keywords_used",
            field=JSONField(blank=True, default=list, verbose_name="사용 키워드"),
        ),
    ]
