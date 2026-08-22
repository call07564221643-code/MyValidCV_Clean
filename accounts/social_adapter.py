import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


logger = logging.getLogger(__name__)


PROVIDER_SCOPES = {
    "google": ["openid", "email", "profile"],
    "linkedin": ["openid", "email", "profile"],
}


class MyValidCVSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Record the standard identity consent represented by a completed OAuth flow."""

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        self._record_social_consent(user, sociallogin.account.provider)
        return user

    def on_authentication_error(
        self, request, provider, error=None, exception=None, extra_context=None
    ):
        """Log the provider's safe error description without OAuth codes or tokens."""
        logger.warning(
            "Social authentication failed provider=%s error=%s exception_type=%s detail=%s",
            provider.id,
            error,
            type(exception).__name__ if exception else "",
            str(exception)[:500] if exception else "",
        )
        return super().on_authentication_error(
            request,
            provider,
            error=error,
            exception=exception,
            extra_context=extra_context,
        )

    @staticmethod
    def _record_social_consent(user, provider):
        from growth.models import ConsentRecord

        ConsentRecord.objects.create(
            user=user,
            purpose="social_login",
            provider=provider,
            scopes=PROVIDER_SCOPES.get(provider, ["openid", "email"]),
            policy_version="social-login-v1",
            evidence={"source": "oauth_callback"},
        )
