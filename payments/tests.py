import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan

from .models import Invoice, PaymentTransaction, PaymentWebhookLog, Refund
from .services import SumUpAPIError, create_stripe_checkout_session, refund_sumup_transaction


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PAYMENT_PROVIDER="sumup",
    SUMUP_API_KEY="sumup-test-key",
    SUMUP_MERCHANT_CODE="MEYUPGAT",
    SUMUP_MODE="sandbox",
)
class SumUpCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sumup-payer", "sumup@example.com", "password")
        self.client.force_login(self.user)
        self.plan = SubscriptionPlan.objects.create(
            code="plus", name="Plus", price=Decimal("4.99"), currency="GBP",
        )

    @patch("payments.views.create_sumup_checkout")
    def test_default_sumup_provider_creates_hosted_checkout(self, create_checkout):
        create_checkout.return_value = {
            "id": "checkout-1", "status": "PENDING",
            "hosted_checkout_url": "https://checkout.sumup.com/pay/checkout-1",
        }
        response = self.client.post(reverse("start_checkout", args=[self.plan.code]))
        self.assertRedirects(
            response, "https://checkout.sumup.com/pay/checkout-1", fetch_redirect_response=False,
        )
        payment = PaymentTransaction.objects.get()
        self.assertEqual(payment.provider, "sumup")
        self.assertEqual(payment.provider_checkout_id, "checkout-1")

    @patch("payments.views.retrieve_sumup_checkout")
    def test_verified_sumup_return_activates_subscription(self, retrieve_checkout):
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, provider="sumup", amount=self.plan.price,
            currency="GBP", status="pending", provider_checkout_id="checkout-paid",
        )
        Invoice.objects.create(
            user=self.user, transaction=payment, invoice_number="SUMUP-PAID",
            amount=payment.amount, currency="GBP", status="open",
        )
        retrieve_checkout.return_value = {
            "id": "checkout-paid", "checkout_reference": str(payment.checkout_reference),
            "merchant_code": "MEYUPGAT", "amount": 4.99, "currency": "GBP", "status": "PAID",
            "transactions": [{"transaction_code": "TX-SUMUP-1"}],
        }
        response = self.client.get(reverse("sumup_return", args=[payment.checkout_reference]))
        self.assertRedirects(response, reverse("payment_receipt", args=[payment.checkout_reference]))
        payment.refresh_from_db()
        self.assertEqual(payment.status, "paid")
        self.assertEqual(payment.provider_transaction_id, "TX-SUMUP-1")
        self.assertEqual(CustomerSubscription.objects.get(user=self.user).status, "active")

    @patch("payments.views.retrieve_sumup_checkout")
    def test_sumup_webhook_verifies_checkout_and_is_idempotent(self, retrieve_checkout):
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, provider="sumup", amount=self.plan.price,
            currency="GBP", status="pending", provider_checkout_id="checkout-hook",
        )
        retrieve_checkout.return_value = {
            "id": "checkout-hook", "checkout_reference": str(payment.checkout_reference),
            "merchant_code": "MEYUPGAT", "amount": "4.99", "currency": "GBP", "status": "PAID",
            "transactions": [],
        }
        payload = {"event_type": "CHECKOUT_STATUS_CHANGED", "id": "checkout-hook"}
        first = self.client.post(reverse("sumup_webhook"), data=json.dumps(payload), content_type="application/json")
        second = self.client.post(reverse("sumup_webhook"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertTrue(second.json()["duplicate"])
        payment.refresh_from_db()
        self.assertEqual(payment.status, "paid")

    @patch("payments.views.retrieve_sumup_checkout")
    def test_mismatched_sumup_checkout_never_activates_access(self, retrieve_checkout):
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, provider="sumup", amount=self.plan.price,
            currency="GBP", status="pending", provider_checkout_id="checkout-mismatch",
        )
        retrieve_checkout.return_value = {
            "id": "checkout-mismatch", "checkout_reference": "wrong-reference",
            "merchant_code": "MEYUPGAT", "amount": 4.99, "currency": "GBP", "status": "PAID",
        }
        response = self.client.get(reverse("sumup_return", args=[payment.checkout_reference]))
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "pending")
        self.assertFalse(CustomerSubscription.objects.filter(user=self.user).exists())

    def test_non_owner_cannot_use_sumup_sandbox_override(self):
        response = self.client.post(reverse("sumup_sandbox_test", args=[self.plan.code]))
        self.assertEqual(response.status_code, 404)

    @patch("payments.services.urllib.request.urlopen")
    def test_sumup_refund_uses_verified_payment_id_and_amount(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"{}"
        urlopen.return_value = response
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, provider="sumup", amount=Decimal("4.99"),
            currency="GBP", status="paid",
            raw_response={"transactions": [{"id": "payment-uuid", "transaction_code": "TX-1"}]},
        )

        self.assertEqual(refund_sumup_transaction(payment, Decimal("1.25")), {})
        request = urlopen.call_args.args[0]
        self.assertIn("/payments/payment-uuid/refunds", request.full_url)
        self.assertEqual(json.loads(request.data), {"amount": 1.25})

    def test_sumup_refund_cannot_exceed_remaining_amount(self):
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, provider="sumup", amount=Decimal("4.99"),
            currency="GBP", status="paid",
            raw_response={"transactions": [{"id": "payment-uuid"}]},
        )
        Refund.objects.create(
            transaction=payment, amount=Decimal("4.00"), reason="Partial refund", status="processed",
        )
        with self.assertRaisesMessage(SumUpAPIError, "remaining refundable"):
            refund_sumup_transaction(payment, Decimal("1.00"))


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
        invoice = Invoice.objects.create(
            user=self.user,
            transaction=transaction,
            invoice_number="MVCV-SUCCESS",
            amount=self.plan.price,
            currency="GBP",
            status="open",
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
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertIsNotNone(invoice.paid_at)
        self.assertIsNotNone(invoice.next_payment_date)
        self.assertEqual(invoice.receipt_email_status, "sent")
        self.assertEqual(len(mail.outbox), 1)

        receipt = self.client.get(response.url)
        self.assertContains(receipt, "Payment confirmed")
        self.assertContains(receipt, "Your subscription is active")

        repeated = self.client.get(reverse("checkout_success", args=[transaction.checkout_reference]))
        self.assertRedirects(repeated, reverse("payment_receipt", args=[transaction.checkout_reference]))
        self.assertEqual(len(mail.outbox), 1)

    def test_pending_transaction_cannot_display_confirmed_receipt(self):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        Invoice.objects.create(
            user=self.user,
            transaction=transaction,
            invoice_number="MVCV-PENDING",
            amount=self.plan.price,
            currency="GBP",
            status="open",
        )

        response = self.client.get(reverse("payment_receipt", args=[transaction.checkout_reference]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "payments/payment_pending.html")
        self.assertNotContains(response, "Payment confirmed")

    def test_success_return_recovers_when_webhook_already_marked_payment_paid(self):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="paid",
        )
        Invoice.objects.create(
            user=self.user,
            transaction=transaction,
            invoice_number="MVCV-PAID",
            amount=self.plan.price,
            currency="GBP",
            status="paid",
        )

        response = self.client.get(reverse("checkout_success", args=[transaction.checkout_reference]))

        self.assertRedirects(response, reverse("payment_receipt", args=[transaction.checkout_reference]))

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
    def test_failed_webhook_processing_can_be_retried(self):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            provider="stripe",
            amount=self.plan.price,
            currency="GBP",
            status="pending",
        )
        payload = json.dumps({
            "id": "evt_retry_checkout",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_retry_checkout",
                "payment_status": "paid",
                "customer": "cus_retry_checkout",
                "subscription": "sub_retry_checkout",
                "metadata": {"checkout_reference": str(transaction.checkout_reference)},
            }},
        }).encode()
        timestamp = int(time.time())
        digest = hmac.new(
            b"whsec_test",
            f"{timestamp}.".encode() + payload,
            hashlib.sha256,
        ).hexdigest()
        signature = f"t={timestamp},v1={digest}"

        with patch("payments.views.activate_paid_transaction", side_effect=RuntimeError("temporary failure")):
            failed = self.client.post(
                reverse("stripe_webhook"),
                data=payload,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE=signature,
            )
        self.assertEqual(failed.status_code, 500)
        log = PaymentWebhookLog.objects.get(event_id="evt_retry_checkout")
        self.assertFalse(log.is_processed)

        retried = self.client.post(
            reverse("stripe_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )
        self.assertEqual(retried.status_code, 200)
        self.assertNotIn("duplicate", retried.json())
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "paid")
        log.refresh_from_db()
        self.assertTrue(log.is_processed)
        self.assertEqual(log.error, "")

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
