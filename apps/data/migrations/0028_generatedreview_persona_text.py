from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0027_generatedreview_model_keywords"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedreview",
            name="persona_text",
            field=models.CharField(blank=True, default="", max_length=200, verbose_name="페르소나 텍스트"),
        ),
    ]
