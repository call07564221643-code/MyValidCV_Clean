from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from governance.models import OrganisationMembership


@login_required(login_url="login")
def partner_dashboard(request):
    memberships = OrganisationMembership.objects.filter(
        user=request.user, is_active=True,
    ).select_related("organisation")
    organisations = []
    for membership in memberships:
        organisation = membership.organisation
        purchases = organisation.bulk_purchases.select_related("plan")
        vouchers = organisation.vouchers.select_related("plan")
        referral = getattr(organisation, "referral_programme", None)
        organisations.append({
            "organisation": organisation,
            "membership": membership,
            "purchases": purchases[:20],
            "voucher_count": vouchers.count(),
            "redemptions": vouchers.aggregate(total=Sum("redemptions"))["total"] or 0,
            "active_vouchers": vouchers.filter(is_active=True)[:20] if membership.role in {"owner", "manager"} else [],
            "referral": referral,
            "commission_total": referral.commissions.filter(status="paid").aggregate(total=Sum("amount"))["total"] if referral else 0,
            "attribution_count": referral.attributions.count() if referral else 0,
        })
    return render(request, "growth/partner_dashboard.html", {"organisations": organisations})
