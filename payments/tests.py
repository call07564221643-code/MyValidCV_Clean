import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan

from .models import PaymentTransaction
from .services import create_stripe_checkout_session


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

    @override_settings(DEBUG=True, STRIPE_MOCK_MODE=True)
    def test_plan_button_route_opens_stripe_mock_checkout(self):
        response = self.client.post(reverse("start_checkout", args=[self.plan.code]))
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

    @override_settings(STRIPE_SECRET_KEY="sk_test_example")
    @patch("payments.services.urllib.request.urlopen")
    def test_checkout_session_is_recurring_and_idempotent(self, urlopen):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        response = MagicMock()
        response.read.return_value = b'{"id":"cs_test","url":"https://checkout.stripe.test"}'
        urlopen.return_value.__enter__.return_value = response
        create_stripe_checkout_session(transaction, "https://example.test/success", "https://example.test/cancel")
        request = urlopen.call_args.args[0]
        payload = parse_qs(request.data.decode())
        self.assertEqual(payload["mode"], ["subscription"])
        self.assertEqual(payload["line_items[0][price_data][recurring][interval]"], ["month"])
        self.assertEqual(
            request.headers["Idempotency-key"],
            f"mvcv-checkout-{transaction.checkout_reference}",
        )

    @override_settings(STRIPE_SECRET_KEY="sk_test_example")
    @patch("payments.services.urllib.request.urlopen")
    def test_checkout_uses_dynamic_price_even_when_plan_has_stripe_price_id(self, urlopen):
        self.plan.stripe_price_id = "price_full_amount"
        self.plan.save(update_fields=["stripe_price_id"])
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        response = MagicMock()
        response.read.return_value = b'{"id":"cs_test","url":"https://checkout.stripe.test"}'
        urlopen.return_value.__enter__.return_value = response
        create_stripe_checkout_session(transaction, "https://example.test/success", "https://example.test/cancel")
        payload = parse_qs(urlopen.call_args.args[0].data.decode())
        self.assertNotIn("line_items[0][price]", payload)
        self.assertEqual(payload["line_items[0][price_data][unit_amount]"], ["499"])

    @override_settings(STRIPE_SECRET_KEY="sk_test_example")
    @patch("payments.services.urllib.request.urlopen")
    def test_discounted_checkout_uses_discounted_dynamic_price(self, urlopen):
        discount = DiscountCode.objects.create(code="HALF", percent_off=50)
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            discount_code=discount,
            provider="stripe",
            amount=Decimal("2.50"),
            currency="GBP",
            status="pending",
        )
        response = MagicMock()
        response.read.return_value = b'{"id":"cs_test","url":"https://checkout.stripe.test"}'
        urlopen.return_value.__enter__.return_value = response
        create_stripe_checkout_session(transaction, "https://example.test/success", "https://example.test/cancel")
        payload = parse_qs(urlopen.call_args.args[0].data.decode())
        self.assertNotIn("line_items[0][price]", payload)
        self.assertEqual(payload["line_items[0][price_data][unit_amount]"], ["250"])

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
            "mode": "subscription",
            "status": "complete",
            "payment_status": "paid",
            "customer": "cus_test_123",
            "subscription": "sub_test_123",
            "metadata": {"checkout_reference": str(transaction.checkout_reference)},
        }
        response = self.client.get(
            reverse("checkout_success", args=[transaction.checkout_reference]),
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
            "id": "evt_checkout_paid",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_webhook",
                "payment_status": "paid",
                "customer": "cus_test_webhook",
                "subscription": "sub_test_webhook",
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
        subscription = CustomerSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_subscription_id, "sub_test_webhook")

        duplicate = self.client.post(
            reverse("stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={digest}",
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
    def test_subscription_deleted_webhook_revokes_paid_access(self):
        self.user.profile.plan = "plus"
        self.user.profile.save(update_fields=["plan"])
        CustomerSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status="active",
            stripe_customer_id="cus_cancel",
            stripe_subscription_id="sub_cancel",
        )
        payload = json.dumps({
            "id": "evt_subscription_deleted",
            "type": "customer.subscription.deleted",
            "data": {"object": {
                "id": "sub_cancel",
                "customer": "cus_cancel",
                "status": "canceled",
                "metadata": {},
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
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "free")
        self.assertEqual(CustomerSubscription.objects.get(user=self.user).status, "cancelled")
