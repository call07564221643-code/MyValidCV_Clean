from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Stage 2 of registration: attach plan/usage data to a new auth User.

    Django creates the core ``User`` first. This signal then creates the
    one-to-one ``UserProfile`` used by dashboards and ATS allowance checks.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Keep the profile link present when an existing auth User is saved."""
    profile, _created = UserProfile.objects.get_or_create(user=instance)
    profile.save()
