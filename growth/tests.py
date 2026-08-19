from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from governance.models import Organisation, OrganisationMembership
from subscriptions.models import SubscriptionPlan

from payments.models import PaymentTransaction
from payments.views import activate_paid_transaction

from .models import (
    AccessVoucher, BulkPurchase, CommissionEntry, PartnerProfile,
    ProviderConnection, ReferralAttribution, ReferralPartner, VoucherRedemption,
)
from .services import VoucherError, redeem_access_voucher


class PartnerAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("student", "student@example.edu", "password")
        self.plan = SubscriptionPlan.objects.create(code="plus", name="Plus", price="9.00")
        self.organisation = Organisation.objects.create(
            name="Example University", slug="example-university", organisation_type="university", status="active"
        )
        self.purchase = BulkPurchase.objects.create(
            organisation=self.organisation, plan=self.plan, quantity=2,
            unit_price="5.00", status="active",
        )
        self.voucher = AccessVoucher.objects.create(
            organisation=self.organisation, bulk_purchase=self.purchase, plan=self.plan,
            code="UNIVERSITY-2026", max_redemptions=2, allowed_email_domain="example.edu",
        )

    def test_voucher_activates_plan_and_allocation_atomically(self):
        subscription = redeem_access_voucher(code="university-2026", user=self.user)
        self.voucher.refresh_from_db()
        self.purchase.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(self.voucher.redemptions, 1)
        self.assertEqual(self.purchase.allocated_quantity, 1)
        self.assertEqual(self.user.profile.plan, "plus")
        self.assertTrue(VoucherRedemption.objects.filter(voucher=self.voucher, user=self.user).exists())

    def test_voucher_rejects_wrong_email_domain(self):
        outsider = User.objects.create_user("outsider", "person@example.com", "password")
        with self.assertRaisesMessage(VoucherError, "restricted"):
            redeem_access_voucher(code=self.voucher.code, user=outsider)

    def test_voucher_cannot_be_redeemed_twice_by_same_user(self):
        redeem_access_voucher(code=self.voucher.code, user=self.user)
        with self.assertRaisesMessage(VoucherError, "already redeemed"):
            redeem_access_voucher(code=self.voucher.code, user=self.user)

    def test_provider_configuration_rejects_secrets(self):
        connection = ProviderConnection(provider="google", configuration={"client_secret": "unsafe"})
        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_partner_workspace_is_scoped_to_membership(self):
        OrganisationMembership.objects.create(
            organisation=self.organisation, user=self.user, role="manager"
        )
        other = Organisation.objects.create(
            name="Other Partner", slug="other-partner", organisation_type="agency"
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("partner_dashboard"))
        self.assertContains(response, "Example University")
        self.assertNotContains(response, "Other Partner")
        self.assertContains(response, "UNIVERSITY-2026")

    def test_verified_payment_creates_configured_referral_commission_once(self):
        PartnerProfile.objects.create(
            organisation=self.organisation, stage="active",
            commission_type="percent", commission_value="10.00",
        )
        partner = ReferralPartner.objects.create(
            organisation=self.organisation, referral_code="example-university", approved_at=timezone.now(),
        )
        ReferralAttribution.objects.create(partner=partner, user=self.user, source="linkedin")
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, amount="9.00", status="pending",
        )
        activate_paid_transaction(payment)
        activate_paid_transaction(payment)
        commission = CommissionEntry.objects.get(partner=partner, transaction=payment)
        self.assertEqual(commission.amount, Decimal("0.90"))
        self.assertEqual(CommissionEntry.objects.count(), 1)
