from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditEvent, ManagementAssignment, Organisation, OrganisationMembership


@override_settings(SECURE_SSL_REDIRECT=False)
class GovernanceTests(TestCase):
    def setUp(self):
        call_command("seed_management_roles", verbosity=0)
        self.owner = User.objects.create_superuser("owner", "owner@example.com", "password")
        self.manager = User.objects.create_user("manager", "manager@example.com", "password")

    def test_assignment_grants_staff_and_group_permissions(self):
        role = Group.objects.get(name="Marketing Manager")
        assignment = ManagementAssignment.objects.create(
            user=self.manager, role=role, assigned_by=self.owner,
        )
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_staff)
        self.assertTrue(self.manager.has_perm("growth.view_marketingcampaign"))
        assignment.is_active = False
        assignment.save()
        self.manager = User.objects.get(pk=self.manager.pk)
        self.assertFalse(self.manager.has_perm("growth.view_marketingcampaign"))
        self.assertFalse(self.manager.is_staff)

    def test_revocation_preserves_independently_privileged_staff(self):
        role = Group.objects.get(name="Marketing Manager")
        assignment = ManagementAssignment.objects.create(user=self.manager, role=role, assigned_by=self.owner)
        self.manager.user_permissions.add(role.permissions.first())
        assignment.is_active = False
        assignment.save()
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_staff)

    def test_one_manager_can_hold_multiple_roles(self):
        for name in ("Marketing Manager", "Growth Analyst"):
            ManagementAssignment.objects.create(user=self.manager, role=Group.objects.get(name=name), assigned_by=self.owner)
        self.assertEqual(self.manager.management_assignments.filter(is_active=True).count(), 2)

    def test_organisation_supports_multiple_individual_members(self):
        organisation = Organisation.objects.create(
            name="Example University", slug="example-university", organisation_type="university"
        )
        second = User.objects.create_user("second", "second@example.com", "password")
        OrganisationMembership.objects.create(organisation=organisation, user=self.manager, role="manager")
        OrganisationMembership.objects.create(organisation=organisation, user=second, role="analyst")
        self.assertEqual(organisation.memberships.count(), 2)

    def test_owner_governance_admin_requires_password_step_up(self):
        self.client.force_login(self.owner)
        protected = reverse("admin:governance_organisation_changelist")
        response = self.client.get(protected)
        self.assertRedirects(response, reverse("owner_governance_unlock") + f"?next={protected}")
        response = self.client.post(reverse("owner_governance_unlock"), {"password": "password", "next": protected})
        self.assertRedirects(response, protected)
        self.assertTrue(AuditEvent.objects.filter(action="owner.governance_unlocked").exists())

    def test_non_owner_cannot_unlock_governance(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("owner_governance_unlock")).status_code, 403)
