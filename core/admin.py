from django.contrib import admin
from .models import Analysis


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'overall_score', 'ats_score', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)
