from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.core import mail
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
        self.assertContains(response, '>Account<', html=False)
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

    def test_login_accepts_email_case_insensitively(self):
        response = self.client.post(reverse('login'), {
            'username': 'CUSTOMER@EXAMPLE.COM',
            'password': 'password',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_form_explains_username_or_email(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'Username or email')

    def test_login_links_to_password_reset(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, reverse('password_reset'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_one_time_link(self):
        response = self.client.post(reverse('password_reset'), {
            'email': 'CUSTOMER@example.com',
        })
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/reset/', mail.outbox[0].body)
        self.assertIn('customer@example.com', mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_does_not_reveal_unknown_email(self):
        response = self.client.post(reverse('password_reset'), {
            'email': 'unknown@example.com',
        })
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_owner_has_separate_report_explorer(self):
        owner = User.objects.create_superuser('owner', 'owner@example.com', 'password')
        self.client.force_login(owner)
        response = self.client.get(reverse('owner_reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Report explorer')
        self.assertContains(response, 'Owner Reports')

    def test_customer_cannot_access_owner_report_explorer(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('owner_reports'))
        self.assertEqual(response.status_code, 403)

    def test_authenticated_user_cannot_return_to_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(reverse('register'), {
            'username': 'another-customer',
            'email': 'CUSTOMER@example.com',
            'password1': 'Secure-password-2026!',
            'password2': 'Secure-password-2026!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account already uses this email address')

    def test_registration_with_email_does_not_require_username(self):
        response = self.client.post(reverse('register'), {
            'username': '',
            'email': 'new.person@example.com',
            'password1': 'Secure-password-2026!',
            'password2': 'Secure-password-2026!',
        })
        self.assertRedirects(response, reverse('dashboard'))
        user = User.objects.get(email='new.person@example.com')
        self.assertTrue(user.username.startswith('newperson'))

    def test_generated_username_is_unique(self):
        User.objects.create_user('newperson', 'existing@example.com', 'password')
        self.client.post(reverse('register'), {
            'username': '',
            'email': 'new.person@example.com',
            'password1': 'Secure-password-2026!',
            'password2': 'Secure-password-2026!',
        })
        user = User.objects.get(email='new.person@example.com')
        self.assertEqual(user.username, 'newperson-2')

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
        self.assertContains(response, 'Enterprise dashboard')

    def test_profile_label_without_active_subscription_does_not_enable_bulk(self):
        self.user.profile.plan = 'enterprise'
        self.user.profile.save(update_fields=['plan'])
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Bulk analysis')
        self.assertContains(response, 'Free dashboard')
