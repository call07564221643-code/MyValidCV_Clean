import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from governance.models import Organisation
from payments.models import PaymentTransaction
from subscriptions.models import SubscriptionPlan


def generate_voucher_code():
    return f"MVCV-{secrets.token_urlsafe(9).upper().replace('_', '').replace('-', '')[:12]}"


class PartnerProfile(models.Model):
    STAGE_CHOICES = [
        ("prospect", "Prospect"), ("contacted", "Contacted"),
        ("proposal", "Proposal"), ("negotiation", "Negotiation"),
        ("approved", "Approved"), ("active", "Active"),
        ("renewal", "Renewal"), ("closed", "Closed"),
    ]
    COMMISSION_CHOICES = [("none", "None"), ("fixed", "Fixed fee"), ("percent", "Percentage")]

    organisation = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name="partner_profile")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="prospect", db_index=True)
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="managed_partners",
    )
    commission_type = models.CharField(max_length=12, choices=COMMISSION_CHOICES, default="none")
    commission_value = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    agreement_reference = models.CharField(max_length=120, blank=True)
    agreement_starts_at = models.DateField(null=True, blank=True)
    agreement_ends_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        permissions = [("approve_partner", "Can approve partner agreements")]

    def __str__(self):
        return self.organisation.name


class BulkPurchase(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"), ("pending", "Pending payment"),
        ("active", "Active"), ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"), ("expired", "Expired"),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT, related_name="bulk_purchases")
    purchaser = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="bulk_purchases")
    transaction = models.ForeignKey(
        PaymentTransaction, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="bulk_purchases",
    )
    quantity = models.PositiveIntegerField()
    allocated_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="GBP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("approve_bulk_purchase", "Can approve bulk purchases")]

    @property
    def remaining_quantity(self):
        return max(0, self.quantity - self.allocated_quantity)

    def __str__(self):
        return f"{self.organisation} · {self.quantity} × {self.plan.name}"


class AccessVoucher(models.Model):
    bulk_purchase = models.ForeignKey(
        BulkPurchase, null=True, blank=True, on_delete=models.CASCADE, related_name="vouchers"
    )
    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT, related_name="vouchers")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="access_vouchers")
    code = models.CharField(max_length=40, unique=True, default=generate_voucher_code)
    campaign_name = models.CharField(max_length=180, blank=True)
    max_redemptions = models.PositiveIntegerField(default=1)
    redemptions = models.PositiveIntegerField(default=0)
    allowed_email_domain = models.CharField(max_length=180, blank=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="access_vouchers_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("issue_access_voucher", "Can issue bulk-access vouchers")]

    def is_available(self):
        now = timezone.now()
        return bool(
            self.is_active and self.valid_from <= now
            and (not self.valid_until or self.valid_until > now)
            and self.redemptions < self.max_redemptions
        )

    def __str__(self):
        return self.code


class VoucherRedemption(models.Model):
    voucher = models.ForeignKey(AccessVoucher, on_delete=models.PROTECT, related_name="redemption_records")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voucher_redemptions")
    redeemed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["voucher", "user"], name="unique_voucher_user_redemption")]
        ordering = ["-redeemed_at"]


class ReferralPartner(models.Model):
    organisation = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name="referral_programme")
    referral_code = models.SlugField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    cookie_days = models.PositiveIntegerField(default=30)
    self_referrals_allowed = models.BooleanField(default=False)
    terms_version = models.CharField(max_length=40, default="affiliate-v1")
    commission_hold_days = models.PositiveIntegerField(default=30)
    minimum_payout = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("25.00"))
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.referral_code

    def is_eligible(self, at=None):
        at = at or timezone.now()
        profile = getattr(self.organisation, "partner_profile", None)
        return bool(
            self.is_active and self.approved_at and self.organisation.status == "active"
            and profile and profile.stage == "active"
            and (not profile.agreement_starts_at or profile.agreement_starts_at <= at.date())
            and (not profile.agreement_ends_at or profile.agreement_ends_at >= at.date())
            and self.agreement_acceptances.filter(terms_version=self.terms_version).exists()
        )


class AffiliateAgreementAcceptance(models.Model):
    partner = models.ForeignKey(ReferralPartner, on_delete=models.PROTECT, related_name="agreement_acceptances")
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    terms_version = models.CharField(max_length=40)
    legal_name = models.CharField(max_length=180)
    country = models.CharField(max_length=2, help_text="ISO two-letter country code.")
    approved_channels = models.JSONField(default=list, blank=True)
    acceptance_ip = models.GenericIPAddressField(null=True, blank=True)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accepted_at"]
        constraints = [models.UniqueConstraint(fields=["partner", "terms_version"], name="unique_partner_terms_acceptance")]

    def __str__(self):
        return f"{self.partner} · {self.terms_version}"


class ReferralAttribution(models.Model):
    partner = models.ForeignKey(ReferralPartner, null=True, blank=True, on_delete=models.SET_NULL, related_name="attributions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="referral_attributions")
    anonymous_id = models.CharField(max_length=64, blank=True, db_index=True)
    landing_path = models.CharField(max_length=500, blank=True)
    source = models.CharField(max_length=120, blank=True)
    medium = models.CharField(max_length=120, blank=True)
    campaign = models.CharField(max_length=180, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    consent_source = models.CharField(max_length=30, default="affiliate_consent")
    converted_at = models.DateTimeField(null=True, blank=True)
    conversion_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-first_seen_at"]


class CommissionEntry(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"), ("approved", "Approved"),
        ("payable", "Payable"), ("paid", "Paid"),
        ("reversed", "Reversed"),
    ]
    partner = models.ForeignKey(ReferralPartner, on_delete=models.PROTECT, related_name="commissions")
    attribution = models.ForeignKey(ReferralAttribution, null=True, blank=True, on_delete=models.SET_NULL)
    transaction = models.ForeignKey(PaymentTransaction, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commissionable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    commission_rate = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="GBP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    matures_at = models.DateTimeField(null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("approve_commission", "Can approve partner commissions")]
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "transaction"],
                condition=models.Q(transaction__isnull=False),
                name="unique_partner_transaction_commission",
            )
        ]


class ConsentRecord(models.Model):
    PURPOSE_CHOICES = [
        ("social_login", "Social login"), ("marketing", "Marketing communications"),
        ("analytics", "Analytics"), ("partner_reporting", "Partner reporting"),
        ("advertising", "Advertising audiences"), ("affiliate_tracking", "Affiliate referral tracking"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consent_records")
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, db_index=True)
    provider = models.CharField(max_length=40, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    policy_version = models.CharField(max_length=40)
    is_granted = models.BooleanField(default=True)
    granted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-granted_at"]
        indexes = [models.Index(fields=["user", "purpose", "is_granted"], name="consent_user_purpose_idx")]


class ProviderConnection(models.Model):
    PROVIDER_CHOICES = [
        ("google", "Google"), ("linkedin", "LinkedIn"),
        ("meta", "Meta / Facebook"), ("tiktok", "TikTok"),
        ("google_analytics", "Google Analytics"),
        ("search_console", "Google Search Console"),
    ]
    STATUS_CHOICES = [("draft", "Draft"), ("connected", "Connected"), ("error", "Error"), ("disabled", "Disabled")]

    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    scopes = models.JSONField(default=list, blank=True)
    external_account_hint = models.CharField(max_length=180, blank=True)
    configuration = models.JSONField(default=dict, blank=True, help_text="Non-secret configuration only.")
    configured_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    connected_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        permissions = [("configure_provider", "Can configure external providers")]

    def __str__(self):
        return self.get_provider_display()

    def clean(self):
        forbidden = {"secret", "password", "token", "api_key", "private_key", "client_secret"}
        keys = {str(key).lower() for key in self.configuration.keys()}
        if keys & forbidden:
            raise ValidationError({"configuration": "Store secrets in protected environment configuration, not this record."})


class MarketingCampaign(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"), ("review", "Awaiting review"),
        ("approved", "Approved"), ("published", "Published"),
        ("paused", "Paused"), ("completed", "Completed"),
    ]
    CHANNEL_CHOICES = [
        ("google", "Google"), ("linkedin", "LinkedIn"),
        ("meta", "Facebook / Instagram"), ("tiktok", "TikTok"),
        ("email", "Email"), ("organic", "Organic / content"),
    ]

    name = models.CharField(max_length=180)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES)
    objective = models.CharField(max_length=180)
    audience_summary = models.TextField(blank=True)
    content_brief = models.TextField(blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="GBP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="campaigns_created")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="campaigns_approved",
    )
    version = models.PositiveIntegerField(default=1)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("approve_campaign", "Can approve marketing campaigns"),
            ("publish_campaign", "Can publish approved marketing campaigns"),
        ]

    def __str__(self):
        return self.name


class CampaignApproval(models.Model):
    DECISION_CHOICES = [("approved", "Approved"), ("changes", "Changes requested"), ("rejected", "Rejected")]
    campaign = models.ForeignKey(MarketingCampaign, on_delete=models.CASCADE, related_name="approval_history")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    campaign_version = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at"]


class AnalyticsEvent(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    organisation = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.SET_NULL)
    anonymous_id = models.CharField(max_length=64, blank=True, db_index=True)
    source = models.CharField(max_length=120, blank=True)
    campaign = models.CharField(max_length=180, blank=True)
    properties = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["name", "-occurred_at"], name="growth_event_name_idx")]
