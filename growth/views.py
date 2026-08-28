from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from governance.models import AuditEvent, OrganisationMembership
from .forms import AffiliateApplicationForm
from .models import AffiliateAgreementAcceptance, AffiliateApplication, ReferralPartner


AFFILIATE_CHANNELS = {
    "website", "blog", "email", "linkedin", "youtube", "facebook", "instagram", "tiktok", "events",
}

ACTIVE_APPLICATION_STATUSES = {
    "submitted", "review", "meeting_requested", "meeting_scheduled", "changes", "approved",
}


def affiliate_guide(request):
    application = None
    if request.user.is_authenticated:
        application = AffiliateApplication.objects.filter(user=request.user).first()
    return render(request, "growth/affiliate_guide.html", {"application": application})


@login_required(login_url="login")
def affiliate_apply(request):
    existing = AffiliateApplication.objects.filter(
        user=request.user, status__in=ACTIVE_APPLICATION_STATUSES,
    ).first()
    if existing:
        messages.info(request, "Your affiliate application is already in progress.")
        return redirect("affiliate_guide")
    form = AffiliateApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.user = request.user
        application.save()
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")
        AuditEvent.objects.create(
            actor=request.user, action="affiliate.application_submitted",
            target_type="AffiliateApplication", target_id=str(application.pk),
            summary=f"Affiliate application submitted by {application.legal_name}.",
            ip_address=ip_address,
        )
        messages.success(request, "Application received. It is pending owner review; no referral code is active yet.")
        return redirect("affiliate_guide")
    return render(request, "growth/affiliate_apply.html", {"form": form})


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
            "commission_pending": referral.commissions.filter(status__in=["pending", "approved", "payable"]).aggregate(total=Sum("amount"))["total"] if referral else 0,
            "attribution_count": referral.attributions.count() if referral else 0,
            "agreement_current": referral.agreement_acceptances.filter(terms_version=referral.terms_version).exists() if referral else False,
        })
    affiliate_channels = [(value, value.replace("_", " ").title()) for value in sorted(AFFILIATE_CHANNELS)]
    return render(request, "growth/partner_dashboard.html", {
        "organisations": organisations, "affiliate_channels": affiliate_channels,
    })


@login_required(login_url="login")
@require_POST
def accept_affiliate_agreement(request, partner_id):
    partner = get_object_or_404(ReferralPartner.objects.select_related("organisation"), pk=partner_id)
    membership = OrganisationMembership.objects.filter(
        organisation=partner.organisation, user=request.user, is_active=True, role__in={"owner", "manager"},
    ).first()
    if not membership:
        return render(request, "dashboard/owner_forbidden.html", status=403)
    legal_name = request.POST.get("legal_name", "").strip()[:180]
    country = request.POST.get("country", "").strip().upper()
    channels = sorted(set(request.POST.getlist("channels")) & AFFILIATE_CHANNELS)
    if not legal_name or len(country) != 2 or not channels or request.POST.get("accept_terms") != "yes":
        messages.error(request, "Enter the legal name, two-letter country code, approved channels and accept the agreement.")
        return redirect("partner_dashboard")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    acceptance, created = AffiliateAgreementAcceptance.objects.get_or_create(
        partner=partner, terms_version=partner.terms_version,
        defaults={
            "accepted_by": request.user, "legal_name": legal_name,
            "country": country, "approved_channels": channels, "acceptance_ip": ip_address,
        },
    )
    if not created:
        messages.info(request, "This agreement version has already been accepted and its audit record was not changed.")
        return redirect("partner_dashboard")
    AuditEvent.objects.create(
        actor=request.user, action="affiliate.agreement_accepted",
        target_type="ReferralPartner", target_id=str(partner.pk),
        summary=f"Affiliate agreement {partner.terms_version} accepted for {partner.organisation.name}.",
        ip_address=ip_address,
    )
    messages.success(request, "Affiliate agreement accepted. Owner approval is still required before referrals can earn commission.")
    return redirect("partner_dashboard")
