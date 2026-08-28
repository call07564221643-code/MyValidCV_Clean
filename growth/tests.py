from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from governance.models import Organisation, OrganisationMembership
from subscriptions.models import SubscriptionPlan

from payments.models import PaymentTransaction, Refund
from payments.views import activate_paid_transaction

from .models import (
    AccessVoucher, AffiliateAgreementAcceptance, AffiliateApplication, BulkPurchase, CommissionEntry, PartnerProfile,
    ProviderConnection, ReferralAttribution, ReferralPartner, VoucherRedemption,
)
from .services import ReferralError, VoucherError, capture_referral_code, redeem_access_voucher


class AffiliateApplicationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("affiliate", "affiliate@example.com", "password")

    def test_public_guide_explains_controlled_journey(self):
        response = self.client.get(reverse("affiliate_guide"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommend responsibly")
        self.assertContains(response, "affiliate-journey-handdrawn.png")
        self.assertContains(response, "20% of the first eligible retained payment")

    def test_application_requires_login(self):
        response = self.client.get(reverse("affiliate_apply"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_submission_is_pending_and_does_not_create_partner(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("affiliate_apply"), {
            "legal_name": "Example Creator Ltd", "applicant_type": "creator", "country": "gb",
            "website": "https://example.com", "public_profiles": "https://linkedin.com/in/example",
            "audience_size": 1200, "audience_countries": "United Kingdom and France",
            "engagement_evidence": "Regular relevant comments and monthly analytics.",
            "audience_description": "Early-career finance professionals.",
            "proposed_channels": ["linkedin", "email"],
            "promotion_plan": "Publish practical CV education with clear affiliate disclosure.",
            "previous_experience": "Career education newsletter.",
            "genuine_audience_confirmed": "on", "compliance_confirmed": "on",
        })
        self.assertRedirects(response, reverse("affiliate_guide"))
        application = AffiliateApplication.objects.get(user=self.user)
        self.assertEqual(application.status, "submitted")
        self.assertEqual(application.country, "GB")
        self.assertFalse(ReferralPartner.objects.exists())

    def test_duplicate_active_application_is_blocked(self):
        AffiliateApplication.objects.create(
            user=self.user, legal_name="Example", applicant_type="creator", country="GB",
            audience_countries="GB", engagement_evidence="Evidence", audience_description="Audience",
            promotion_plan="Plan", genuine_audience_confirmed=True, compliance_confirmed=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("affiliate_apply"))
        self.assertRedirects(response, reverse("affiliate_guide"))
        self.assertEqual(AffiliateApplication.objects.count(), 1)


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
        Organisation.objects.create(
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
        affiliate_owner = User.objects.create_user("affiliate-owner", "owner@example.edu", "password")
        OrganisationMembership.objects.create(organisation=self.organisation, user=affiliate_owner, role="owner")
        AffiliateAgreementAcceptance.objects.create(
            partner=partner, accepted_by=affiliate_owner, terms_version=partner.terms_version,
            legal_name="Example University", country="GB", approved_channels=["website"],
        )
        ReferralAttribution.objects.create(partner=partner, user=self.user, source="linkedin")
        payment = PaymentTransaction.objects.create(
            user=self.user, plan=self.plan, amount="9.00", status="pending",
        )
        activate_paid_transaction(payment)
        activate_paid_transaction(payment)
        commission = CommissionEntry.objects.get(partner=partner, transaction=payment)
        self.assertEqual(commission.amount, Decimal("0.90"))
        self.assertEqual(commission.commissionable_amount, Decimal("9.00"))
        self.assertEqual(commission.commission_rate, Decimal("10.00"))
        self.assertGreater(commission.matures_at, timezone.now())
        self.assertEqual(CommissionEntry.objects.count(), 1)

        Refund.objects.create(transaction=payment, amount="9.00", reason="Customer request", status="processed")
        commission.refresh_from_db()
        self.assertEqual(commission.status, "reversed")

    def test_checkout_referral_code_requires_approved_current_agreement(self):
        PartnerProfile.objects.create(
            organisation=self.organisation, stage="active", commission_type="percent", commission_value="20.00",
        )
        partner = ReferralPartner.objects.create(
            organisation=self.organisation, referral_code="creator-code", approved_at=timezone.now(),
        )
        with self.assertRaises(ReferralError):
            capture_referral_code(code=partner.referral_code, user=self.user)
        affiliate_owner = User.objects.create_user("creator-owner", "creator@example.com", "password")
        AffiliateAgreementAcceptance.objects.create(
            partner=partner, accepted_by=affiliate_owner, terms_version=partner.terms_version,
            legal_name="Creator Ltd", country="GB", approved_channels=["youtube"],
        )
        attribution = capture_referral_code(code=partner.referral_code, user=self.user)
        self.assertEqual(attribution.consent_source, "customer_entered_code")
        self.assertGreater(attribution.expires_at, timezone.now())

    def test_partner_owner_accepts_versioned_agreement(self):
        PartnerProfile.objects.create(
            organisation=self.organisation, stage="active", commission_type="percent", commission_value="20.00",
        )
        partner = ReferralPartner.objects.create(
            organisation=self.organisation, referral_code="agreement-code", approved_at=timezone.now(),
        )
        affiliate_owner = User.objects.create_user("agreement-owner", "agreement@example.edu", "password")
        OrganisationMembership.objects.create(organisation=self.organisation, user=affiliate_owner, role="owner")
        self.client.force_login(affiliate_owner)
        response = self.client.post(reverse("accept_affiliate_agreement", args=[partner.id]), {
            "legal_name": "Example University", "country": "gb",
            "channels": ["website", "linkedin"], "accept_terms": "yes",
        })
        self.assertRedirects(response, reverse("partner_dashboard"))
        acceptance = AffiliateAgreementAcceptance.objects.get(partner=partner)
        self.assertEqual(acceptance.country, "GB")
        self.assertEqual(acceptance.terms_version, "affiliate-v1")

    def test_affiliate_link_requires_separate_referral_consent(self):
        PartnerProfile.objects.create(
            organisation=self.organisation, stage="active", commission_type="percent", commission_value="20.00",
        )
        partner = ReferralPartner.objects.create(
            organisation=self.organisation, referral_code="consent-code", approved_at=timezone.now(),
        )
        affiliate_owner = User.objects.create_user("consent-owner", "consent@example.edu", "password")
        AffiliateAgreementAcceptance.objects.create(
            partner=partner, accepted_by=affiliate_owner, terms_version=partner.terms_version,
            legal_name="Example University", country="GB", approved_channels=["website"],
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("home") + "?ref=consent-code")
        self.assertContains(response, "Allow referral tracking")
        self.assertFalse(ReferralAttribution.objects.filter(user=self.user).exists())
        self.client.post(reverse("referral_consent"), {"choice": "granted", "next": reverse("home")}, follow=True)
        attribution = ReferralAttribution.objects.get(user=self.user)
        self.assertEqual(attribution.partner, partner)
        self.assertEqual(attribution.consent_source, "affiliate_consent")
