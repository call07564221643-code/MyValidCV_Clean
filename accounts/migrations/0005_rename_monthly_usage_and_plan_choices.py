from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_seed_social_auth_providers")]

    operations = [
        migrations.RenameField(
            model_name="userprofile",
            old_name="analyses_today",
            new_name="analyses_this_month",
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="analyses_this_month",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="plan",
            field=models.CharField(
                choices=[("free", "Free"), ("plus", "Plus"), ("enterprise", "Enterprise")],
                default="free",
                max_length=20,
            ),
        ),
    ]
