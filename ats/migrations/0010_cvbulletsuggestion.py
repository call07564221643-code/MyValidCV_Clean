from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ats", "0009_jobfamily_qualification_roletemplate_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CVBulletSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0)),
                ("fingerprint", models.CharField(max_length=64)),
                ("original_text", models.TextField()),
                ("proposed_text", models.TextField()),
                ("edited_text", models.TextField(blank=True)),
                ("evidence_terms", models.JSONField(blank=True, default=list)),
                ("evidence_passage", models.TextField(blank=True)),
                ("rationale", models.CharField(max_length=300)),
                ("has_measure", models.BooleanField(default=False)),
                ("measurement_prompt", models.CharField(blank=True, max_length=220)),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("accepted", "Accepted"), ("edited", "Candidate-edited"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ats_result", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bullet_suggestions", to="ats.atsresult")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cv_bullet_suggestions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["position", "id"],
                "indexes": [models.Index(fields=["user", "ats_result", "status"], name="bullet_user_result_status_idx")],
                "constraints": [models.UniqueConstraint(fields=("ats_result", "fingerprint"), name="unique_result_bullet_suggestion")],
            },
        ),
    ]
