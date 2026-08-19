from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


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
