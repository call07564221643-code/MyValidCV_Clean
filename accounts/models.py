from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile for subscription and usage tracking."""
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    analyses_today = models.IntegerField(default=0)
    last_reset = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} - {self.plan}"

    def get_analysis_limit(self) -> int:
        """Get daily analysis limit based on plan."""
        if self.plan == 'free':
            return 2
        elif self.plan == 'professional':
            return 5
        elif self.plan == 'enterprise':
            return 200  # monthly, simplified
        return 0
