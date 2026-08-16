from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("ats", "0007_applicationreminder_reminder_user_sent_idx_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="GeneratedCoverLetter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("ats_result", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="generated_cover_letter", to="ats.atsresult")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generated_cover_letters", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        )
    ]
