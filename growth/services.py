from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from subscriptions.models import CustomerSubscription

from .models import AccessVoucher, CommissionEntry, ReferralAttribution, VoucherRedemption


class VoucherError(ValueError):
    pass


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
    attribution = ReferralAttribution.objects.filter(
        user=transaction.user, partner__is_active=True, converted_at__isnull=True,
    ).select_related("partner__organisation__partner_profile").order_by("first_seen_at").first()
    if not attribution:
        return None
    partner = attribution.partner
    attribution.converted_at = timezone.now()
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
    if profile.commission_type == "fixed":
        amount = profile.commission_value
    else:
        amount = (transaction.amount * profile.commission_value / Decimal("100")).quantize(Decimal("0.01"))
    commission, _created = CommissionEntry.objects.get_or_create(
        partner=partner, transaction=transaction,
        defaults={"attribution": attribution, "amount": amount, "currency": transaction.currency},
    )
    return commission
