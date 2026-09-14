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
        self.assertContains(response, "affiliate-journey-handdrawn-transparent.png")
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
            "engagement_evidence": "Across the last three months our posts receive regular relevant comments shares saves and direct questions. Monthly analytics show consistent engagement from genuine career-focused readers seeking practical employment and CV guidance.",
            "audience_description": "Our audience consists mainly of early-career finance professionals and final-year students in the United Kingdom. They follow us for practical career education application guidance interview preparation and explanations of finance roles. They regularly ask how to tailor their CV evidence to specific vacancies and would benefit from a transparent validation tool.",
            "proposed_channels": ["linkedin", "email"],
            "primary_channel": "linkedin", "linkedin_url": "https://linkedin.com/in/example",
            "linkedin_audience": 1200, "email_url": "https://example.com/newsletter", "email_audience": 600,
            "promotion_plan": "We will publish practical CV education twice each month and demonstrate how applicants can compare evidence with a real role. Every promotional post will begin with a clear affiliate advertising disclosure. We will use educational examples avoid employment guarantees answer questions responsibly and review performance monthly before increasing publication frequency.",
            "previous_experience": "Career education newsletter.",
            "genuine_audience_confirmed": "on", "compliance_confirmed": "on",
        })
        self.assertRedirects(response, reverse("affiliate_application_status"))
        application = AffiliateApplication.objects.get(user=self.user)
        self.assertEqual(application.status, "submitted")
        self.assertEqual(application.country, "GB")
        self.assertEqual(application.channel_details["linkedin"]["audience"], 1200)
        self.assertGreaterEqual(application.suitability_score, 65)
        self.assertFalse(ReferralPartner.objects.exists())

    def test_duplicate_active_application_is_blocked(self):
        AffiliateApplication.objects.create(
            user=self.user, legal_name="Example", applicant_type="creator", country="GB",
            audience_countries="GB", engagement_evidence="Evidence", audience_description="Audience",
            promotion_plan="Plan", genuine_audience_confirmed=True, compliance_confirmed=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("affiliate_apply"))
        self.assertRedirects(response, reverse("affiliate_application_status"))
        self.assertEqual(AffiliateApplication.objects.count(), 1)

    def test_selected_social_channel_requires_public_url(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("affiliate_apply"), {
            "legal_name": "Creator", "applicant_type": "creator", "country": "GB",
            "audience_size": 1000, "audience_countries": "United Kingdom",
            "engagement_evidence": "Genuine engagement evidence covering recent posts comments shares saves replies clicks views and a consistent three month reporting period for this application review.",
            "audience_description": "A relevant audience of students graduates jobseekers and career changers who regularly request practical guidance about CV evidence job descriptions applications recruitment processes and responsible use of career technology in the United Kingdom and Europe.",
            "proposed_channels": ["tiktok"], "primary_channel": "tiktok",
            "promotion_plan": "We will publish responsible educational videos that explain CV evidence and role matching. Every commercial video will clearly disclose the affiliate relationship before the recommendation. We will avoid employment guarantees misleading scores spam self referrals and any claims that the service replaces professional advice.",
            "genuine_audience_confirmed": "on", "compliance_confirmed": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter the public URL for your selected tiktok channel")

    def test_status_centre_shows_reference_and_next_steps(self):
        application = AffiliateApplication.objects.create(
            user=self.user, legal_name="Example", applicant_type="creator", country="GB",
            audience_countries="GB", engagement_evidence="Evidence", audience_description="Audience",
            promotion_plan="Plan", genuine_audience_confirmed=True, compliance_confirmed=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("affiliate_application_status"))
        self.assertContains(response, f"MVCV-AFF-{application.pk:06d}")
        self.assertContains(response, "What happens next")

    def test_owner_affiliate_dashboard_is_permission_protected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("affiliate_owner_dashboard")).status_code, 403)
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        self.assertEqual(self.client.get(reverse("affiliate_owner_dashboard")).status_code, 200)


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
