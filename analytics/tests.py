from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class WebsiteHealthTests(TestCase):
    def test_test_accounts_are_excluded_from_production_user_kpis(self):
        owner = User.objects.create_superuser("owner", "owner@example.com", "password")
        User.objects.create_user("customer", "customer@example.com", "password")
        demo = User.objects.create_user("demo", "demo@example.com", "password")
        demo.profile.is_test_data = True
        demo.profile.save(update_fields=["is_test_data"])

        self.client.force_login(owner)
        response = self.client.get(reverse("website_health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["usage"]["users_total"], 2)
        self.assertEqual(response.context["usage"]["profiles_total"], 2)
