import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ats", "0013_enterprisebatch_sender_email")]

    operations = [
        migrations.CreateModel(
            name="EnterprisePilot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("session_key", models.CharField(db_index=True, max_length=40)),
                ("business_email", models.EmailField(db_index=True, max_length=254)),
                ("job_title", models.CharField(max_length=150)),
                ("company", models.CharField(blank=True, max_length=150)),
                ("job_description", models.TextField()),
                ("mandatory_requirements", models.TextField(blank=True)),
                ("retention_acknowledged_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="EnterprisePilotCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("candidate_label", models.CharField(max_length=40)),
                ("cv_file", models.FileField(upload_to="enterprise_pilots/")),
                ("score", models.IntegerField(default=0)),
                ("matched_skills", models.TextField(blank=True)),
                ("missing_skills", models.TextField(blank=True)),
                ("mandatory_matched", models.JSONField(blank=True, default=list)),
                ("mandatory_missing", models.JSONField(blank=True, default=list)),
                ("mandatory_pass", models.BooleanField(default=True)),
                ("rank", models.PositiveIntegerField(default=0)),
                ("pilot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidates", to="ats.enterprisepilot")),
            ],
            options={"ordering": ["rank", "-score"]},
        ),
    ]
