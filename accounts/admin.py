from django.contrib import admin
from .models import SocialAuthProvider, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'analyses_today', 'created_at')
    list_filter = ('plan', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'last_reset')


@admin.register(SocialAuthProvider)
class SocialAuthProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'is_active', 'is_configured', 'sort_order', 'updated_at')
    list_filter = ('is_active', 'is_configured', 'created_at')
    search_fields = ('name', 'key', 'admin_notes')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'is_configured', 'sort_order')
