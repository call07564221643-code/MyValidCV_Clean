from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from governance.models import ManagementAssignment


@override_settings(SECURE_SSL_REDIRECT=False)
class ManagementDashboardTests(TestCase):
    def setUp(self):
        call_command("seed_management_roles", verbosity=0)
        self.manager = User.objects.create_user("manager", "manager@example.com", "password")

    def test_customer_cannot_access_management_workspace(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("management_dashboard")).status_code, 403)

    def test_manager_sees_only_assigned_operational_area(self):
        ManagementAssignment.objects.create(
            user=self.manager, role=Group.objects.get(name="Marketing Manager")
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse("management_dashboard"))
        self.assertContains(response, "Campaigns")
        self.assertNotContains(response, "Partner commissions")
        self.assertNotContains(response, "Consent records")

    def test_staff_login_redirects_to_management_not_owner(self):
        ManagementAssignment.objects.create(
            user=self.manager, role=Group.objects.get(name="Growth Analyst")
        )
        response = self.client.post(reverse("login"), {"username": "manager", "password": "password"})
        self.assertRedirects(response, reverse("management_dashboard"))


@override_settings(SECURE_SSL_REDIRECT=False, GOOGLE_ANALYTICS_ID="G-TEST123")
class PublicGrowthFoundationTests(TestCase):
    def test_robots_and_sitemap_are_public(self):
        robots = self.client.get(reverse("robots_txt"))
        self.assertContains(robots, "Sitemap:")
        self.assertContains(robots, "Disallow: /owner/")
        sitemap = self.client.get(reverse("sitemap_xml"))
        self.assertContains(sitemap, "<urlset")
        self.assertContains(sitemap, reverse("pricing"))

    def test_analytics_does_not_load_before_consent(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "googletagmanager.com")
        response = self.client.post(
            reverse("analytics_consent"), {"choice": "granted", "next": reverse("home")}, follow=True
        )
        self.assertContains(response, "googletagmanager.com")
