from django.contrib import admin

from .models import ExperienceFeedback


@admin.register(ExperienceFeedback)
class ExperienceFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "rating",
        "feature",
        "user",
        "moderation_status",
        "testimonial_consent",
        "created_at",
    )
    list_filter = ("rating", "feature", "moderation_status", "testimonial_consent")
    search_fields = ("comment", "user__username", "user__email", "session_key")
    readonly_fields = (
        "user",
        "feature",
        "context_id",
        "session_key",
        "rating",
        "categories",
        "comment",
        "page_path",
        "testimonial_consent",
        "public_identity",
        "created_at",
        "updated_at",
    )
