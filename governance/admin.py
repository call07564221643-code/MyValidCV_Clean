from django.contrib import admin

from .models import AuditEvent, ManagementAssignment, Organisation, OrganisationMembership
from .forms import OptimisticLockAdminForm


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    form = OptimisticLockAdminForm
    list_display = ("name", "organisation_type", "status", "primary_contact", "updated_at")
    list_filter = ("organisation_type", "status")
    search_fields = ("name", "slug", "primary_contact__email")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("primary_contact",)
    readonly_fields = ("version",)


@admin.register(OrganisationMembership)
class OrganisationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organisation", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active", "organisation__organisation_type")
    search_fields = ("user__username", "user__email", "organisation__name")
    autocomplete_fields = ("user", "organisation", "invited_by")


@admin.register(ManagementAssignment)
class ManagementAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_active", "assigned_by", "assigned_at", "revoked_at")
    list_filter = ("is_active", "role")
    search_fields = ("user__username", "user__email", "role__name")
    autocomplete_fields = ("user", "assigned_by")
    readonly_fields = ("assigned_at", "revoked_at")

    def save_model(self, request, obj, form, change):
        if not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="management.role_assigned" if obj.is_active else "management.role_revoked",
            target_type="auth.User",
            target_id=str(obj.user_id),
            summary=f"{obj.role.name} {'assigned to' if obj.is_active else 'revoked from'} {obj.user}",
        )


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id", "summary")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "actor__email", "action", "summary", "target_id")
    readonly_fields = tuple(field.name for field in AuditEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
