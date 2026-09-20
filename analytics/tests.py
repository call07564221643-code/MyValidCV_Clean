from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from ats.models import CVStorage

from .models import (
    FinanceFeedConnection,
    FinancialEntry,
    NotificationAttempt,
    OperationalAlert,
    PlatformOperationsSettings,
)
from .services.alerts import evaluate_storage_pressure


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

    def test_finance_feed_separates_recorded_expenses_from_forecast(self):
        owner = User.objects.create_superuser("finance-owner", "finance@example.com", "password")
        FinancialEntry.objects.create(
            direction="income", category="Consulting", description="Manual income",
            amount=Decimal("100.00"), status="reconciled", entered_by=owner,
        )
        FinancialEntry.objects.create(
            direction="expense", category="Hosting", description="Supplier invoice",
            amount=Decimal("30.00"), status="recorded", entered_by=owner,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("website_health"))

        finance = response.context["mini_finance"]
        self.assertEqual(finance["other_income_30_days"], Decimal("100.00"))
        self.assertEqual(finance["recorded_expenses_30_days"], Decimal("30.00"))
        self.assertEqual(finance["recorded_profit_30_days"], Decimal("70.00"))

    def test_finance_feed_configuration_rejects_database_secrets(self):
        connection = FinanceFeedConnection(
            name="Unsafe", provider="sumup", configuration={"api_key": "must-not-be-stored"}
        )
        with self.assertRaisesMessage(Exception, "environment variables"):
            connection.full_clean()

    def test_storage_warning_uses_each_accounts_actual_plan_limit(self):
        owner = User.objects.create_superuser("capacity-owner", "capacity@example.com", "password")
        customer = User.objects.create_user("capacity-customer", "customer2@example.com", "password")
        CVStorage.objects.update_or_create(
            user=customer,
            defaults={"storage_limit": 5 * 1024 * 1024, "used_storage": 4 * 1024 * 1024},
        )
        PlatformOperationsSettings.objects.create(
            alert_email="owner@example.com",
            warning_storage_percent=70,
            critical_storage_percent=90,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse("website_health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["usage"]["storage_warning_count"], 1)
        self.assertEqual(response.context["usage"]["storage_critical_count"], 0)
        self.assertEqual(response.context["usage"]["storage_percent"], 80.0)

    def test_operations_settings_require_provider_and_e164_number_for_whatsapp(self):
        operations = PlatformOperationsSettings(
            email_enabled=False,
            whatsapp_enabled=True,
            mobile_number="07700900123",
            messaging_provider="disabled",
        )

        with self.assertRaises(ValidationError) as raised:
            operations.full_clean()

        self.assertIn("mobile_number", raised.exception.message_dict)
        self.assertIn("messaging_provider", raised.exception.message_dict)

    def test_operations_settings_are_singleton(self):
        PlatformOperationsSettings.objects.create(email_enabled=False)

        with self.assertRaises(ValidationError):
            PlatformOperationsSettings.objects.create(email_enabled=False)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_storage_alert_is_deduplicated_and_email_is_audited(self):
        customer = User.objects.create_user("alert-customer", "alert-customer@example.com", "password")
        CVStorage.objects.update_or_create(
            user=customer,
            defaults={"storage_limit": 1000, "used_storage": 950},
        )
        PlatformOperationsSettings.objects.create(
            alert_email="owner@example.com",
            warning_storage_percent=70,
            critical_storage_percent=90,
        )

        first = evaluate_storage_pressure(send_notifications=True)
        second = evaluate_storage_pressure(send_notifications=True)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(OperationalAlert.objects.count(), 1)
        self.assertEqual(second.occurrence_count, 2)
        self.assertEqual(len(mail.outbox), 1)
        attempt = NotificationAttempt.objects.get()
        self.assertEqual(attempt.status, "sent")
        self.assertEqual(attempt.destination_hint, "ow***@example.com")
        self.assertNotIn("alert-customer", first.message)

    def test_storage_alert_resolves_when_pressure_clears(self):
        customer = User.objects.create_user("recovery-customer", "recovery@example.com", "password")
        storage, _created = CVStorage.objects.update_or_create(
            user=customer,
            defaults={"storage_limit": 1000, "used_storage": 950},
        )
        PlatformOperationsSettings.objects.create(email_enabled=False)
        alert = evaluate_storage_pressure()
        storage.used_storage = 100
        storage.save(update_fields=["used_storage"])

        result = evaluate_storage_pressure()

        alert.refresh_from_db()
        self.assertIsNone(result)
        self.assertEqual(alert.status, "resolved")
        self.assertIsNotNone(alert.resolved_at)
