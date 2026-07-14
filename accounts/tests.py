from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import CustomerSubscription, SubscriptionPlan


@override_settings(SECURE_SSL_REDIRECT=False)
class CustomerNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('customer', 'customer@example.com', 'password')

    def test_authenticated_navigation_is_reports_and_settings(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '>Reports<', html=False)
        self.assertContains(response, '>Settings<', html=False)
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

    def test_free_dashboard_does_not_show_bulk_analysis(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Bulk analysis')
        self.assertNotContains(response, 'New bulk analysis')

    def test_validation_page_is_focused_engine(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('ats_analyse'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ATS validation engine')
        self.assertContains(response, 'Paste job text')
        self.assertContains(response, 'Job advert URL')
        self.assertContains(response, 'Upload advert')
        self.assertNotContains(response, 'Recent reports')
        self.assertNotContains(response, 'Create cover letter</button>')

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'customer',
            'password': 'password',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_authenticated_user_cannot_return_to_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_active_enterprise_subscription_enables_enterprise_dashboard(self):
        plan = SubscriptionPlan.objects.create(
            code='enterprise',
            name='Enterprise',
            price='49.00',
            monthly_bulk_cv_limit=50,
        )
        CustomerSubscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            current_period_end=timezone.now() + timedelta(days=30),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Enterprise candidate intelligence')
        self.assertContains(response, 'Bulk analysis')
        self.assertContains(response, 'Enterprise access')
        self.assertContains(response, 'Subscription started')
        self.assertContains(response, 'Next payment renewal')

    def test_profile_label_without_active_subscription_does_not_enable_bulk(self):
        self.user.profile.plan = 'enterprise'
        self.user.profile.save(update_fields=['plan'])
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Bulk analysis')
        self.assertContains(response, 'Free plan services')
