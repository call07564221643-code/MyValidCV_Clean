from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("growth", "0006_affiliateapplication")]
    operations = [
        migrations.AddField(model_name="affiliateapplication", name="channel_details", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="affiliateapplication", name="risk_flags", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="affiliateapplication", name="score_breakdown", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="affiliateapplication", name="suitability_score", field=models.PositiveSmallIntegerField(default=0)),
    ]
