from django.contrib import admin

from .models import (
    ApplicationReminder,
    ATSResult,
    CV,
    CVStorage,
    EnterpriseBatch,
    EnterpriseCandidateResult,
    GeneratedCoverLetter,
    GeneratedCV,
    JobRole,
    JobFamily,
    Qualification,
    RoleTemplate,
    RoleTemplateQualification,
    RoleTemplateSkill,
    Skill,
)

admin.site.register(GeneratedCoverLetter)


@admin.register(CVStorage)
class CVStorageAdmin(admin.ModelAdmin):
    list_display = ("user", "storage_limit", "used_storage", "auto_delete_enabled", "updated_at")
    list_filter = ("auto_delete_enabled", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("public_id", "used_storage", "created_at", "updated_at")


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "file_size", "validation_status", "is_valid_cv", "uploaded_at")
    list_filter = ("validation_status", "is_valid_cv", "uploaded_at")
    search_fields = ("title", "original_filename", "user__username", "user__email")
    readonly_fields = ("public_id", "file_size", "mime_type", "uploaded_at", "updated_at")


@admin.register(ATSResult)
class ATSResultAdmin(admin.ModelAdmin):
    list_display = ("job_title", "cv", "job_role", "user", "score", "status", "created_at")
    list_filter = ("status", "score", "created_at")
    search_fields = ("job_title", "cv__title", "user__username", "user__email")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(JobRole)
class JobRoleAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "user", "source_type", "deadline", "created_at")
    list_filter = ("source_type", "deadline", "created_at")
    search_fields = ("title", "company", "user__username", "description")


@admin.register(JobFamily)
class JobFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name", "description")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "normalized_name", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "normalized_name", "aliases")


@admin.register(Qualification)
class QualificationAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "issuing_body", "is_license", "created_at")
    list_filter = ("category", "is_license")
    search_fields = ("name", "normalized_name", "issuing_body", "aliases")


class RoleTemplateSkillInline(admin.TabularInline):
    model = RoleTemplateSkill
    extra = 0
    autocomplete_fields = ("skill",)


class RoleTemplateQualificationInline(admin.TabularInline):
    model = RoleTemplateQualification
    extra = 0
    autocomplete_fields = ("qualification",)


@admin.register(RoleTemplate)
class RoleTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "job_family", "seniority_level", "created_at")
    list_filter = ("job_family", "seniority_level")
    search_fields = ("title", "normalized_title", "aliases", "description")
    autocomplete_fields = ("job_family",)
    inlines = (RoleTemplateSkillInline, RoleTemplateQualificationInline)


@admin.register(RoleTemplateSkill)
class RoleTemplateSkillAdmin(admin.ModelAdmin):
    list_display = ("role_template", "skill", "importance")
    list_filter = ("importance", "role_template__job_family")
    search_fields = ("role_template__title", "skill__name")
    autocomplete_fields = ("role_template", "skill")


@admin.register(RoleTemplateQualification)
class RoleTemplateQualificationAdmin(admin.ModelAdmin):
    list_display = ("role_template", "qualification", "importance")
    list_filter = ("importance", "role_template__job_family", "qualification__is_license")
    search_fields = ("role_template__title", "qualification__name")
    autocomplete_fields = ("role_template", "qualification")


@admin.register(GeneratedCV)
class GeneratedCVAdmin(admin.ModelAdmin):
    list_display = ("title", "original_cv", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "original_cv__title", "user__username", "content")
    readonly_fields = ("created_at",)


@admin.register(ApplicationReminder)
class ApplicationReminderAdmin(admin.ModelAdmin):
    list_display = ("job_role", "user", "reminder_date", "is_sent", "created_at")
    list_filter = ("is_sent", "reminder_date", "created_at")
    search_fields = ("job_role__title", "user__username", "note")


@admin.register(EnterpriseBatch)
class EnterpriseBatchAdmin(admin.ModelAdmin):
    list_display = ("title", "job_role", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "job_role__title", "user__username", "notes")


@admin.register(EnterpriseCandidateResult)
class EnterpriseCandidateResultAdmin(admin.ModelAdmin):
    list_display = ("rank", "candidate_name", "batch", "score", "created_at")
    list_filter = ("score", "created_at")
    search_fields = ("candidate_name", "batch__title", "matched_skills", "missing_skills")
