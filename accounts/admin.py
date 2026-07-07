from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'analyses_today', 'created_at')
    list_filter = ('plan', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'last_reset')
