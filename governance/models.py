from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone


class Organisation(models.Model):
    TYPE_CHOICES = [
        ("enterprise", "Enterprise customer"),
        ("university", "University or college"),
        ("agency", "Agency"),
        ("creator", "Content creator"),
        ("job_fair", "Job fair"),
        ("public_sector", "Public-sector organisation"),
        ("charity", "Charity or career service"),
        ("other", "Other partner"),
    ]
    STATUS_CHOICES = [
        ("prospect", "Prospect"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("closed", "Closed"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=190, unique=True)
    organisation_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="prospect")
    primary_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="primary_contact_organisations",
    )
    website = models.URLField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["name"]
        permissions = [("approve_organisation", "Can approve or suspend organisations")]

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Organisation owner"),
        ("manager", "Manager"),
        ("recruiter", "Recruiter"),
        ("finance", "Finance"),
        ("analyst", "Analyst"),
        ("viewer", "Read only"),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organisation_memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="organisation_invitations_sent",
    )
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "user"], name="unique_org_membership")
        ]
        ordering = ["organisation", "user__username"]

    def __str__(self):
        return f"{self.user} · {self.organisation} ({self.role})"


class ManagementAssignment(models.Model):
    """Auditable assignment of a Django permission group to one manager."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="management_assignments")
    role = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="management_assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="management_roles_assigned",
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="unique_management_assignment")]
        permissions = [("manage_roles", "Can assign management roles")]

    def save(self, *args, **kwargs):
        if not self.is_active and not self.revoked_at:
            self.revoked_at = timezone.now()
        if self.is_active:
            self.revoked_at = None
        super().save(*args, **kwargs)
        if self.is_active:
            self.user.groups.add(self.role)
            if not self.user.is_staff:
                self.user.is_staff = True
                self.user.save(update_fields=["is_staff"])
        else:
            self.user.groups.remove(self.role)

    def __str__(self):
        return f"{self.user} · {self.role}"

    def delete(self, *args, **kwargs):
        user, role = self.user, self.role
        result = super().delete(*args, **kwargs)
        user.groups.remove(role)
        return result


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="governance_events",
    )
    action = models.CharField(max_length=120, db_index=True)
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("view_sensitive_audit", "Can view sensitive audit metadata")]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} · {self.action}"
