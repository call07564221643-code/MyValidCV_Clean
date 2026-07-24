import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExperienceFeedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("feature", models.CharField(choices=[("ats", "ATS result"), ("maya", "Maya adviser"), ("general", "General platform")], max_length=20)),
                ("context_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("session_key", models.CharField(blank=True, db_index=True, max_length=40)),
                ("rating", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ("categories", models.JSONField(blank=True, default=list)),
                ("comment", models.TextField(blank=True, max_length=1200)),
                ("page_path", models.CharField(blank=True, max_length=255)),
                ("testimonial_consent", models.BooleanField(default=False)),
                ("public_identity", models.CharField(choices=[("anonymous", "Verified MyValidCV user"), ("first_name", "First name"), ("initials", "Initials")], default="anonymous", max_length=20)),
                ("moderation_status", models.CharField(choices=[("private", "Private feedback"), ("pending", "Pending testimonial review"), ("approved", "Approved testimonial"), ("rejected", "Not approved")], db_index=True, default="private", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="experience_feedback", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["feature", "-created_at"], name="feedback_feature_created_idx"),
                    models.Index(fields=["moderation_status", "-created_at"], name="feedback_status_created_idx"),
                ],
            },
        ),
    ]
