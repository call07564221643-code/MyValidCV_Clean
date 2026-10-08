from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserProfile
from subscriptions.models import CustomerSubscription

from .models import AccessVoucher, CommissionEntry, ReferralAttribution, ReferralPartner, VoucherRedemption


class VoucherError(ValueError):
    pass


class ReferralError(ValueError):
    pass


def capture_referral_code(*, code, user, source="checkout_code"):
    """Attach an approved referral to a customer without relying on marketing cookies."""
    partner = ReferralPartner.objects.select_related(
        "organisation", "organisation__partner_profile",
    ).filter(referral_code__iexact=(code or "").strip()).first()
    if not partner or not partner.is_eligible():
        raise ReferralError("This referral code is invalid or is not currently active.")
    if (
        not partner.self_referrals_allowed
        and partner.organisation.memberships.filter(user=user, is_active=True).exists()
    ):
        raise ReferralError("A partner cannot use its own referral code.")
    existing = ReferralAttribution.objects.filter(user=user, converted_at__isnull=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()
    if existing:
        return existing
    return ReferralAttribution.objects.create(
        partner=partner, user=user, source=source,
        expires_at=timezone.now() + timedelta(days=partner.cookie_days),
        consent_source="customer_entered_code" if source == "checkout_code" else "analytics_consent",
    )


@transaction.atomic
def redeem_access_voucher(*, code, user):
    """Redeem once with row locking; never oversubscribe a partner allocation."""
    voucher = AccessVoucher.objects.select_for_update().select_related(
        "plan", "bulk_purchase"
    ).filter(code__iexact=code.strip()).first()
    if not voucher or not voucher.is_available():
        raise VoucherError("This access voucher is invalid, exhausted or expired.")
    if voucher.allowed_email_domain:
        user_domain = (user.email.rsplit("@", 1)[-1] if "@" in user.email else "").lower()
        if user_domain != voucher.allowed_email_domain.lower().lstrip("@"):
            raise VoucherError("This voucher is restricted to another email domain.")
    if VoucherRedemption.objects.filter(voucher=voucher, user=user).exists():
        raise VoucherError("This account has already redeemed this voucher.")

    now = timezone.now()
    period_end = voucher.valid_until or (now + timedelta(days=30))
    subscription, _created = CustomerSubscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": voucher.plan,
            "status": "active",
            "started_at": now,
            "current_period_end": period_end,
            "cancelled_at": None,
            "admin_notes": f"Activated by partner voucher {voucher.code}",
        },
    )
    VoucherRedemption.objects.create(
        voucher=voucher, user=user, expires_at=period_end,
    )
    voucher.redemptions += 1
    voucher.save(update_fields=["redemptions"])
    if voucher.bulk_purchase_id:
        purchase = voucher.bulk_purchase.__class__.objects.select_for_update().get(pk=voucher.bulk_purchase_id)
        if purchase.allocated_quantity >= purchase.quantity:
            raise VoucherError("The associated bulk allocation is exhausted.")
        purchase.allocated_quantity += 1
        if purchase.allocated_quantity == purchase.quantity:
            purchase.status = "fulfilled"
        purchase.save(update_fields=["allocated_quantity", "status", "updated_at"])
    UserProfile.objects.update_or_create(user=user, defaults={"plan": voucher.plan.code})
    return subscription


def record_paid_referral_conversion(transaction):
    """Create one commission after verified payment; never infer consent or self-referrals."""
    now = timezone.now()
    if transaction.status != "paid" or transaction.amount <= 0:
        return None
    attribution = ReferralAttribution.objects.select_for_update().filter(
        user=transaction.user, partner__is_active=True, converted_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now)).select_related(
        "partner__organisation__partner_profile"
    ).order_by("first_seen_at").first()
    if transaction.affiliate_partner_id:
        # Payment snapshots bind the discount and commission to the same affiliate.
        attribution = ReferralAttribution.objects.select_for_update().filter(
            user=transaction.user, partner_id=transaction.affiliate_partner_id, converted_at__isnull=True,
        ).order_by("first_seen_at").first()
    if not attribution:
        return None
    partner = attribution.partner
    if not partner.is_eligible(now):
        return None
    attribution.converted_at = now
    attribution.conversion_reference = str(transaction.checkout_reference)
    attribution.save(update_fields=["converted_at", "conversion_reference"])
    if (
        not partner.self_referrals_allowed
        and partner.organisation.memberships.filter(user=transaction.user, is_active=True).exists()
    ):
        return None
    profile = getattr(partner.organisation, "partner_profile", None)
    if not profile or profile.commission_type == "none" or profile.commission_value <= 0:
        return None
    if transaction.affiliate_partner_id:
        rate = transaction.affiliate_commission_rate
        amount = (transaction.amount * rate / Decimal("100")).quantize(Decimal("0.01"))
    elif profile.commission_type == "fixed":
        amount = min(profile.commission_value, transaction.amount)
        rate = Decimal("0.00")
    else:
        amount = (transaction.amount * profile.commission_value / Decimal("100")).quantize(Decimal("0.01"))
        rate = profile.commission_value
    commission, _created = CommissionEntry.objects.get_or_create(
        partner=partner, transaction=transaction,
        defaults={
            "attribution": attribution, "amount": amount,
            "commissionable_amount": transaction.amount, "commission_rate": rate,
            "currency": transaction.currency,
            "matures_at": now + timedelta(days=partner.commission_hold_days),
        },
    )
    return commission


def prepare_checkout_terms(*, plan, user, discount_code="", referral_code=""):
    from subscriptions.models import DiscountCode
    discount_code = discount_code.strip()
    referral_code = referral_code.strip()
    # Accept the affiliate code in either code box; never stack discounts.
    if not referral_code and ReferralPartner.objects.filter(referral_code__iexact=discount_code).exists():
        referral_code, discount_code = discount_code, ""
    if referral_code and discount_code:
        raise ReferralError("Use either an affiliate code or a discount code; discounts cannot be combined.")
    if referral_code:
        partner = ReferralPartner.objects.select_related("organisation__partner_profile").filter(
            referral_code__iexact=referral_code).first()
        if not partner or not partner.is_eligible():
            raise ReferralError("This affiliate code is inactive, expired or awaiting agreement acceptance.")
        if not partner.self_referrals_allowed and partner.organisation.memberships.filter(user=user, is_active=True).exists():
            raise ReferralError("An affiliate cannot use its own code.")
        percent = partner.customer_discount_percent
        if percent < 0 or percent > 100:
            raise ReferralError("This code has invalid discount terms.")
        amount = (plan.price * (Decimal("100") - percent) / Decimal("100")).quantize(Decimal("0.01"))
        return None, amount, partner
    if discount_code:
        discount = DiscountCode.objects.filter(code__iexact=discount_code).first()
        if not discount or not discount.is_valid_now() or (discount.amount_off and discount.currency != plan.currency):
            raise ReferralError("This discount code is not valid for this purchase.")
        return discount, discount.apply_to(plan.price), None
    return None, plan.price, None


@transaction.atomic
def attach_checkout_affiliate(payment, partner):
    if not partner:
        return
    from django.contrib.auth import get_user_model
    get_user_model().objects.select_for_update().get(pk=payment.user_id)
    payment.affiliate_partner = partner
    payment.affiliate_commission_rate = partner.organisation.partner_profile.commission_value
    payment.affiliate_discount_percent = partner.customer_discount_percent
    payment.original_amount = payment.plan.price
    payment.save(update_fields=["affiliate_partner", "affiliate_commission_rate", "affiliate_discount_percent", "original_amount", "updated_at"])
    if not ReferralAttribution.objects.filter(user=payment.user, partner=partner, converted_at__isnull=True).exists():
        ReferralAttribution.objects.create(user=payment.user, partner=partner, source="checkout_code",
            consent_source="customer_entered_code",
            expires_at=partner.valid_until or timezone.now() + timedelta(days=partner.cookie_days))


def reverse_referral_commission(transaction, reason="Customer payment refunded"):
    """Reverse unpaid commission when the underlying revenue is no longer retained."""
    return CommissionEntry.objects.filter(
        transaction=transaction, status__in=["pending", "approved", "payable", "paid"],
    ).update(status="reversed", reversal_reason=reason[:255])
