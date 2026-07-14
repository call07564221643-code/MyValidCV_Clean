from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class CustomerNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('customer', 'customer@example.com', 'password')

    def test_authenticated_navigation_is_reports_and_settings(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Reports<', html=False)
        self.assertContains(response, '>Settings<', html=False)
        self.assertNotContains(response, '>Plans<', html=False)
        self.assertNotContains(response, '>Health<', html=False)
        self.assertNotContains(response, '>Admin<', html=False)

    def test_settings_page_updates_customer_details(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_settings'), {
            'first_name': 'Alex',
            'last_name': 'Taylor',
            'email': 'alex@example.com',
        })
        self.assertRedirects(response, reverse('account_settings'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'alex@example.com')

    def test_landing_page_has_start_now_and_no_enterprise_link(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Start Now')
        self.assertNotContains(response, '>Enterprise<', html=False)
