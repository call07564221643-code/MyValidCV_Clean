from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import FinanceFeedConnection, FinancialEntry


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
