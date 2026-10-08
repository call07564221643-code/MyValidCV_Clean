from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import Permission, User
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from governance.models import AuditEvent, Organisation
from payments.models import PaymentTransaction, Refund
from payments.views import activate_paid_transaction
from subscriptions.models import SubscriptionPlan
from .affiliate_workflow import approve_application, manage_code
from .models import AffiliateApplication, AffiliateAgreementAcceptance, AffiliatePayoutDetails, CommissionEntry
from .payouts import PayoutForm, payout_cipher, save_payout_details
from .services import ReferralError, prepare_checkout_terms, attach_checkout_affiliate


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   AFFILIATE_PAYOUT_ENCRYPTION_KEY=Fernet.generate_key().decode())
class AffiliateWorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("reviewer", "owner@example.com", "password")
        self.owner.user_permissions.add(Permission.objects.get(codename="review_affiliate_application"))
        self.affiliate = User.objects.create_user("affiliate", "affiliate@example.com", "password")
        self.customer = User.objects.create_user("customer", "customer@example.com", "password")
        self.app = AffiliateApplication.objects.create(user=self.affiliate, legal_name="Example Affiliate", country="GB", applicant_type="creator")
        self.plan = SubscriptionPlan.objects.create(code="enterprise", name="Enterprise", price=Decimal("100.00"))

    def approve(self):
        with self.captureOnCommitCallbacks(execute=True):
            return approve_application(self.app.pk, self.owner, "Owner approved a meeting waiver")

    def activate(self):
        partner = self.approve()
        save_payout_details(partner, {"account_holder": "Example", "bank_name": "Example bank", "iban": "GB82WEST12345698765432"})
        self.client.force_login(self.affiliate)
        response = self.client.post(reverse("accept_affiliate_agreement", args=[partner.pk]),
            {"legal_name": "Example", "country": "GB", "channels": ["podcast"], "accept_terms": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(partner.is_eligible())
        return partner

    def test_approval_waiver_provisions_once_and_emails(self):
        with self.assertRaises(ValueError):
            approve_application(self.app.pk, self.owner)
        partner = self.approve()
        self.assertEqual(approve_application(self.app.pk, self.owner).pk, partner.pk)
        self.assertEqual(Organisation.objects.count(), 1)
        self.assertEqual(partner.customer_discount_percent, 20)
        self.assertEqual(partner.valid_until.year, timezone.now().year + 1)
        self.assertEqual(partner.organisation.partner_profile.commission_value, Decimal("20.00"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(partner.referral_code, mail.outbox[0].body)
        self.assertFalse(partner.is_eligible())

    def test_permissions_and_no_admin_escalation(self):
        with self.assertRaises(PermissionDenied):
            approve_application(self.app.pk, self.customer, "waiver")
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(reverse("affiliate_owner_dashboard"), {"action": "approve", "application_id": self.app.pk}).status_code, 403)
        self.assertFalse(self.owner.is_staff)

    def test_owner_dashboard_approval_and_partner_display(self):
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("affiliate_owner_dashboard"), {"action": "approve", "application_id": self.app.pk, "waiver_reason": "Exception"})
        self.assertEqual(response.status_code, 302)
        self.app.refresh_from_db()
        self.client.force_login(self.affiliate)
        self.assertContains(self.client.get(reverse("partner_dashboard")), self.app.partner.referral_code)

    def test_agreement_requires_bank_and_snapshots_terms(self):
        partner = self.approve()
        self.client.force_login(self.affiliate)
        data = {"legal_name": "Example", "country": "GB", "channels": ["podcast"], "accept_terms": "yes"}
        self.client.post(reverse("accept_affiliate_agreement", args=[partner.pk]), data)
        self.assertFalse(AffiliateAgreementAcceptance.objects.exists())
        save_payout_details(partner, {"account_holder": "Example", "bank_name": "Bank", "iban": "GB82WEST12345698765432"})
        self.client.post(reverse("accept_affiliate_agreement", args=[partner.pk]), data)
        terms = AffiliateAgreementAcceptance.objects.get().commercial_terms
        self.assertEqual(terms["customer_discount_percent"], 20)
        self.assertEqual(terms["commission_percent"], "20.00")
        self.assertEqual(terms["valid_until"], partner.valid_until.isoformat())

    def test_encrypted_bank_validation_and_access(self):
        partner = self.approve()
        form = PayoutForm({"account_holder": "Example", "bank_name": "Bank", "iban": "GB82 WEST 1234 5698 7654 32"})
        self.assertTrue(form.is_valid(), form.errors)
        saved = save_payout_details(partner, form.cleaned_data)
        self.assertNotIn("GB82", saved.encrypted_details)
        self.assertIn("GB82", payout_cipher().decrypt(saved.encrypted_details.encode()).decode())
        self.assertEqual(saved.account_last_four, "5432")
        self.assertFalse(PayoutForm({"account_holder": "X", "bank_name": "Y", "swift": "DEUTDEFF"}).is_valid())
        self.assertFalse(PayoutForm({"account_holder": "X", "bank_name": "Y", "iban": "GB00WEST12345698765432"}).is_valid())
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(reverse("save_affiliate_payout", args=[partner.pk]), form.data).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("affiliate_payout_review", args=[partner.pk])).status_code, 403)
        self.owner.user_permissions.add(Permission.objects.get(codename="approve_commission"))
        response = self.client.get(reverse("affiliate_payout_review", args=[partner.pk]))
        self.assertContains(response, "GB82WEST12345698765432")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_discount_and_commission_use_discounted_amount_and_refund(self):
        partner = self.activate()
        discount, amount, selected = prepare_checkout_terms(plan=self.plan, user=self.customer, referral_code=partner.referral_code.upper())
        self.assertEqual(amount, Decimal("80.00"))
        payment = PaymentTransaction.objects.create(user=self.customer, plan=self.plan, amount=amount, status="pending")
        attach_checkout_affiliate(payment, selected)
        activate_paid_transaction(payment)
        first_end = self.customer.customer_subscription.current_period_end
        activate_paid_transaction(payment)
        self.customer.customer_subscription.refresh_from_db()
        self.assertEqual(self.customer.customer_subscription.current_period_end, first_end)
        commission = CommissionEntry.objects.get(transaction=payment)
        self.assertEqual(commission.amount, Decimal("16.00"))
        self.assertEqual(commission.commission_rate, Decimal("20.00"))
        self.assertEqual(CommissionEntry.objects.count(), 1)
        Refund.objects.create(transaction=payment, amount=Decimal("80.00"), status="processed")
        commission.refresh_from_db()
        self.assertEqual(commission.status, "reversed")

    def test_enterprise_preview_and_no_stacking_or_self_referral(self):
        partner = self.activate()
        self.client.force_login(self.customer)
        response = self.client.get(reverse("checkout_preview", args=["enterprise"]), {"referral_code": partner.referral_code})
        self.assertEqual(response.json()["total"], "80.00")
        with self.assertRaises(ReferralError):
            prepare_checkout_terms(plan=self.plan, user=self.customer, referral_code=partner.referral_code, discount_code="OTHER")
        with self.assertRaises(ReferralError):
            prepare_checkout_terms(plan=self.plan, user=self.affiliate, referral_code=partner.referral_code)

    def test_expiry_and_warning_before_cancellation(self):
        partner = self.activate()
        with self.assertRaises(ValueError):
            manage_code(partner.pk, self.owner, "cancel")
        manage_code(partner.pk, self.owner, "warn", "Please correct your advertising disclosure.")
        self.client.force_login(self.affiliate)
        self.assertContains(self.client.get(reverse("partner_dashboard")), "Please correct your advertising disclosure.")
        manage_code(partner.pk, self.owner, "cancel")
        with self.assertRaises(ReferralError):
            prepare_checkout_terms(plan=self.plan, user=self.customer, referral_code=partner.referral_code)
        partner.refresh_from_db()
        self.assertIsNotNone(partner.cancelled_at)
        self.assertTrue(AuditEvent.objects.filter(action="affiliate.code_cancel").exists())

    def test_expired_code_rejected(self):
        partner = self.activate()
        partner.valid_until = timezone.now() - timedelta(seconds=1)
        partner.save(update_fields=["valid_until"])
        with self.assertRaises(ReferralError):
            prepare_checkout_terms(plan=self.plan, user=self.customer, referral_code=partner.referral_code)

    def test_email_failure_is_visible_and_retryable(self):
        with patch("growth.affiliate_workflow.send_mail", side_effect=RuntimeError("offline")):
            partner = self.approve()
        partner.refresh_from_db()
        self.assertTrue(partner.email_error)
        self.assertIsNone(partner.code_emailed_at)
        with self.captureOnCommitCallbacks(execute=True):
            manage_code(partner.pk, self.owner, "resend")
        partner.refresh_from_db()
        self.assertIsNotNone(partner.code_emailed_at)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_console_email_backend_is_not_reported_as_delivery(self):
        partner = self.approve()
        partner.refresh_from_db()
        self.assertIsNone(partner.code_emailed_at)
        self.assertTrue(partner.email_error)
