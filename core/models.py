"""Shared public-experience records."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ExperienceFeedback(models.Model):
    FEATURE_CHOICES = [
        ("ats", "ATS result"),
        ("maya", "Maya adviser"),
        ("general", "General platform"),
    ]
    MODERATION_CHOICES = [
        ("private", "Private feedback"),
        ("pending", "Pending testimonial review"),
        ("approved", "Approved testimonial"),
        ("rejected", "Not approved"),
    ]
    IDENTITY_CHOICES = [
        ("anonymous", "Verified MyValidCV user"),
        ("first_name", "First name"),
        ("initials", "Initials"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="experience_feedback",
    )
    feature = models.CharField(max_length=20, choices=FEATURE_CHOICES)
    context_id = models.PositiveBigIntegerField(null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    categories = models.JSONField(default=list, blank=True)
    comment = models.TextField(blank=True, max_length=1200)
    page_path = models.CharField(max_length=255, blank=True)
    testimonial_consent = models.BooleanField(default=False)
    public_identity = models.CharField(
        max_length=20,
        choices=IDENTITY_CHOICES,
        default="anonymous",
    )
    moderation_status = models.CharField(
        max_length=20,
        choices=MODERATION_CHOICES,
        default="private",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["feature", "-created_at"], name="feedback_feature_created_idx"),
            models.Index(fields=["moderation_status", "-created_at"], name="feedback_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_feature_display()} - {self.rating}/5"

    @property
    def public_name(self):
        if not self.user or self.public_identity == "anonymous":
            return "Verified MyValidCV user"
        full_name = self.user.get_full_name().strip()
        if self.public_identity == "first_name":
            return self.user.first_name or self.user.username
        if self.public_identity == "initials" and full_name:
            return "".join(part[0].upper() for part in full_name.split() if part)
        return "Verified MyValidCV user"
