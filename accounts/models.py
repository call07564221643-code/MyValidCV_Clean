"""Identity-adjacent database models.

Django's built-in User remains the authentication source of truth. UserProfile
adds product plan/usage data through a one-to-one foreign-key relationship.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    """Extended user profile for subscription and usage tracking."""
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('plus', 'Plus'),
        ('enterprise', 'Enterprise'),
    ]

    # Database link: deleting the Django User also deletes this dependent profile.
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    analyses_this_month = models.PositiveIntegerField(default=0)
    last_reset = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} - {self.plan}"

    def get_analysis_limit(self) -> int:
        """Compatibility wrapper around the central entitlement policy."""
        from subscriptions.services import get_entitlements
        return get_entitlements(self.user).analysis_limit

    def get_cv_limit(self) -> int:
        """Compatibility wrapper around the central entitlement policy."""
        from subscriptions.services import get_entitlements
        return get_entitlements(self.user).cv_limit

    def reset_daily_usage_if_needed(self) -> None:
        """Reset the legacy usage counter at the start of a new calendar month."""
        today = timezone.localdate()
        if (self.last_reset.year, self.last_reset.month) != (today.year, today.month):
            self.analyses_this_month = 0
            self.last_reset = timezone.now()
            self.save(update_fields=['analyses_this_month', 'last_reset'])

    def can_run_analysis(self) -> bool:
        self.reset_daily_usage_if_needed()
        return self.analyses_this_month < self.get_analysis_limit()

    def record_analysis(self) -> None:
        self.reset_daily_usage_if_needed()
        self.analyses_this_month += 1
        self.save(update_fields=['analyses_this_month', 'last_reset'])


class SocialAuthProvider(models.Model):
    """Configurable social login provider shown on login and registration pages."""

    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('linkedin', 'LinkedIn'),
        ('facebook', 'Facebook'),
        ('microsoft', 'Microsoft'),
        ('github', 'GitHub'),
    ]

    key = models.SlugField(max_length=40, unique=True, choices=PROVIDER_CHOICES)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)
    is_configured = models.BooleanField(
        default=False,
        help_text='Enable after OAuth client ID, secret, callback URL, and scopes are configured.',
    )
    icon_label = models.CharField(max_length=8, blank=True, help_text='Short label shown in the button, e.g. G or in.')
    sort_order = models.PositiveIntegerField(default=0)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Social login provider'
        verbose_name_plural = 'Social login providers'

    def __str__(self):
        status = 'configured' if self.is_configured else 'pending setup'
        return f'{self.name} ({status})'
