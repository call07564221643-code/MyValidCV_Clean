from django.conf import settings
from django.core.management.base import BaseCommand

from growth.models import ProviderConnection


PROVIDERS = {
    "google": {
        "required_settings": ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
        "callback_url": "https://www.myvalidcv.com/accounts/google/login/callback/",
        "permitted_data": ["verified email", "name", "profile picture", "locale"],
    },
    "linkedin": {
        "required_settings": ["LINKEDIN_OAUTH_CLIENT_ID", "LINKEDIN_OAUTH_CLIENT_SECRET"],
        "callback_url": "https://www.myvalidcv.com/accounts/oidc/linkedin/login/callback/",
        "permitted_data": ["verified email", "name", "profile picture", "locale"],
    },
    "google_analytics": {
        "required_settings": ["GOOGLE_ANALYTICS_ID"],
        "consent_required": True,
    },
    "search_console": {
        "required_settings": ["GOOGLE_SITE_VERIFICATION"],
    },
    "meta": {
        "required_settings": ["META_APP_ID", "META_APP_SECRET", "META_PIXEL_ID"],
        "consent_required": True,
    },
    "tiktok": {
        "required_settings": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_PIXEL_ID"],
        "consent_required": True,
    },
}


class Command(BaseCommand):
    help = "Create non-secret provider setup records for the owner and integration manager."

    def handle(self, *args, **options):
        for provider, configuration in PROVIDERS.items():
            required = configuration["required_settings"]
            configured = all(bool(getattr(settings, name, "")) for name in required)
            connection, created = ProviderConnection.objects.get_or_create(
                provider=provider,
                defaults={
                    "status": "draft",
                    "configuration": {**configuration, "credentials_present": configured},
                },
            )
            if not created:
                merged = dict(connection.configuration)
                for key, value in configuration.items():
                    merged.setdefault(key, value)
                merged["credentials_present"] = configured
                connection.configuration = merged
                connection.save(update_fields=["configuration", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Growth providers synchronized: {len(PROVIDERS)}."))
