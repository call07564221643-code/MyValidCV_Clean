from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ats", "0010_cvbulletsuggestion"),
    ]

    operations = [
        migrations.AddField(
            model_name="cvbulletsuggestion",
            name="applied_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cvbulletsuggestion",
            name="applied_text",
            field=models.TextField(blank=True),
        ),
    ]
