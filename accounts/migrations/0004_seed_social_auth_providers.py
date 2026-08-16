from django.db import migrations


def seed_social_providers(apps, schema_editor):
    SocialAuthProvider = apps.get_model("accounts", "SocialAuthProvider")
    defaults = [
        {
            "key": "google",
            "name": "Google",
            "icon_label": "G",
            "is_active": True,
            "is_configured": False,
            "sort_order": 10,
            "admin_notes": "Add Google OAuth client ID, secret, callback URL, and scopes before marking configured.",
        },
        {
            "key": "linkedin",
            "name": "LinkedIn",
            "icon_label": "in",
            "is_active": True,
            "is_configured": False,
            "sort_order": 20,
            "admin_notes": "Add LinkedIn OAuth client ID, secret, callback URL, and scopes before marking configured.",
        },
        {
            "key": "facebook",
            "name": "Facebook",
            "icon_label": "f",
            "is_active": False,
            "is_configured": False,
            "sort_order": 30,
            "admin_notes": "Inactive by default. Enable only after Facebook OAuth app setup is complete.",
        },
    ]
    for provider in defaults:
        SocialAuthProvider.objects.update_or_create(
            key=provider["key"],
            defaults=provider,
        )


def reverse_seed_social_providers(apps, schema_editor):
    SocialAuthProvider = apps.get_model("accounts", "SocialAuthProvider")
    SocialAuthProvider.objects.filter(key__in=["google", "linkedin", "facebook"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_socialauthprovider"),
    ]

    operations = [
        migrations.RunPython(seed_social_providers, reverse_seed_social_providers),
    ]
