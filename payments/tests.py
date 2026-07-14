import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from subscriptions.models import SubscriptionPlan

from .models import PaymentTransaction


@override_settings(SECURE_SSL_REDIRECT=False)
class StripeCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("payer", "payer@example.com", "password")
        self.client.force_login(self.user)
        self.plan = SubscriptionPlan.objects.create(
            code="plus",
            name="Plus",
            price=Decimal("4.99"),
            currency="GBP",
        )

    @override_settings(STRIPE_MOCK_MODE=True)
    def test_plan_button_route_opens_stripe_mock_checkout(self):
        response = self.client.post(reverse("start_stripe_checkout", args=[self.plan.code]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/stripe_mock_checkout.html")
        transaction = PaymentTransaction.objects.get()
        self.assertEqual(transaction.provider, "stripe")
        self.assertEqual(transaction.amount, Decimal("4.99"))

    @override_settings(STRIPE_MOCK_MODE=False)
    def test_mock_checkout_is_unavailable_in_live_mode(self):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        response = self.client.get(reverse("stripe_mock_checkout", args=[transaction.checkout_reference]))
        self.assertEqual(response.status_code, 404)

    @override_settings(STRIPE_MOCK_MODE=False, STRIPE_SECRET_KEY="sk_test_example")
    @patch("payments.views.retrieve_stripe_checkout_session")
    def test_success_return_requires_verified_paid_session(self, retrieve_session):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            provider_checkout_id="cs_test_123",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        retrieve_session.return_value = {
            "id": "cs_test_123",
            "payment_status": "paid",
            "metadata": {"checkout_reference": str(transaction.checkout_reference)},
        }
        response = self.client.get(
            reverse("stripe_success", args=[transaction.checkout_reference]),
            {"session_id": "cs_test_123"},
        )
        self.assertEqual(response.status_code, 302)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "paid")
        self.assertEqual(UserProfile.objects.get(user=self.user).plan, "plus")

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
    def test_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            reverse("stripe_webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=invalid",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
    def test_signed_paid_webhook_activates_subscription(self):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {
                "payment_status": "paid",
                "metadata": {"checkout_reference": str(transaction.checkout_reference)},
            }},
        }).encode()
        timestamp = int(time.time())
        digest = hmac.new(
            b"whsec_test",
            f"{timestamp}.".encode() + payload,
            hashlib.sha256,
        ).hexdigest()
        response = self.client.post(
            reverse("stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={digest}",
        )
        self.assertEqual(response.status_code, 200)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "paid")
