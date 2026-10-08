from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from governance.models import AuditEvent, OrganisationMembership
from .forms import AffiliateApplicationForm, CHANNEL_CHOICES
from .payouts import PayoutForm, save_payout_details
from .affiliate_workflow import approve_application, manage_code
from .models import AffiliateAgreementAcceptance, AffiliateApplication, ReferralPartner


AFFILIATE_CHANNELS = {value for value, label in CHANNEL_CHOICES}

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
        return redirect("affiliate_application_status")
    form = AffiliateApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.user = request.user
        application.calculate_suitability()
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
        return redirect("affiliate_application_status")
    return render(request, "growth/affiliate_apply.html", {"form": form})


@login_required(login_url="login")
def affiliate_application_status(request):
    application = AffiliateApplication.objects.filter(user=request.user).order_by("-created_at").first()
    if not application:
        return redirect("affiliate_apply")
    stages = ["submitted", "review", "meeting_requested", "meeting_scheduled", "approved"]
    current_step = stages.index(application.status) + 1 if application.status in stages else 1
    return render(request, "growth/affiliate_application_status.html", {
        "application": application, "current_step": current_step,
    })


@login_required(login_url="login")
def affiliate_owner_dashboard(request):
    if not (request.user.is_superuser or request.user.has_perm("growth.review_affiliate_application")):
        return render(request, "dashboard/owner_forbidden.html", status=403)
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "approve":
                approve_application(request.POST.get("application_id"), request.user, request.POST.get("waiver_reason", ""))
                messages.success(request, "Application approved. Partner and one-year code created; email delivery attempted.")
            elif action == "meeting_complete":
                notes = request.POST.get("meeting_notes", "").strip()
                if not notes:
                    raise ValueError("Enter meeting notes before recording completion.")
                with transaction.atomic():
                    application = AffiliateApplication.objects.select_for_update().get(pk=request.POST.get("application_id"))
                    if application.status in {"declined", "withdrawn", "approved"}:
                        raise ValueError("This application is not awaiting a meeting.")
                    application.meeting_status = "completed"
                    application.meeting_notes = notes[:4000]
                    application.reviewed_by = request.user
                    application.save(update_fields=["meeting_status", "meeting_notes", "reviewed_by", "updated_at"])
                    AuditEvent.objects.create(actor=request.user, action="affiliate.meeting_completed",
                        target_type="AffiliateApplication", target_id=str(application.pk), summary="Meeting recorded as completed by reviewer.")
                messages.success(request, "Meeting completion recorded. You can now approve and issue the code.")
            else:
                manage_code(request.POST.get("partner_id"), request.user, action, request.POST.get("warning_message", ""))
                messages.success(request, "Affiliate code action recorded.")
        except (ValueError, AffiliateApplication.DoesNotExist, ReferralPartner.DoesNotExist) as exc:
            messages.error(request, str(exc))
        return redirect("affiliate_owner_dashboard")
    applications = AffiliateApplication.objects.select_related("user", "reviewed_by").order_by(
        "-suitability_score", "created_at",
    )
    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        applications = applications.filter(status=selected_status)
    partners = ReferralPartner.objects.select_related(
        "organisation", "organisation__partner_profile",
    ).annotate(
        uses=Count("attributions", distinct=True),
        conversions=Count("attributions", filter=models.Q(attributions__converted_at__isnull=False), distinct=True),
    ).order_by("-created_at")
    for partner in partners:
        totals = partner.commissions.exclude(status="reversed").aggregate(
            revenue=Sum("commissionable_amount"), commission=Sum("amount"))
        partner.gross_revenue = totals["revenue"]
        partner.commission_generated = totals["commission"]
    return render(request, "growth/affiliate_owner_dashboard.html", {
        "applications": applications, "partners": partners,
        "status_choices": AffiliateApplication.STATUS_CHOICES, "selected_status": selected_status,
    })


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
            "eligible": referral.is_eligible() if referral else False,
            "payout_form": PayoutForm(),
            "payout_saved": hasattr(referral, "payout_details") if referral else False,
        })
    affiliate_channels = [(value, value.replace("_", " ").title()) for value in sorted(AFFILIATE_CHANNELS)]
    return render(request, "growth/partner_dashboard.html", {
        "organisations": organisations, "affiliate_channels": affiliate_channels,
        "now": timezone.now(),
    })


@login_required(login_url="login")
@require_POST
@transaction.atomic
def accept_affiliate_agreement(request, partner_id):
    partner = get_object_or_404(ReferralPartner.objects.select_related("organisation"), pk=partner_id)
    membership = OrganisationMembership.objects.filter(
        organisation=partner.organisation, user=request.user, is_active=True, role__in={"owner", "manager"},
    ).first()
    if not membership:
        return render(request, "dashboard/owner_forbidden.html", status=403)
    if partner.terms_version == "affiliate-20-v2" and not hasattr(partner, "payout_details"):
        messages.error(request, "Save your bank payout details before accepting the agreement.")
        return redirect("partner_dashboard")
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
            "commercial_terms": {
                "commission_percent": str(partner.organisation.partner_profile.commission_value),
                "customer_discount_percent": partner.customer_discount_percent,
                "valid_until": partner.valid_until.isoformat() if partner.valid_until else None,
                "basis": "20% of each eligible checkout payment retained by MyValidCV after the customer discount; automatic subscription renewals are excluded; discounts do not stack.",
                "hold_days": partner.commission_hold_days, "minimum_payout": str(partner.minimum_payout),
                "cancellation": "Administrator may cancel after publishing a warning in the affiliate dashboard.",
            },
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
    messages.success(request, "Affiliate agreement accepted. Your dashboard shows whether the code is active.")
    return redirect("partner_dashboard")


@login_required(login_url="login")
@require_POST
def save_affiliate_payout(request, partner_id):
    from django.core.exceptions import ImproperlyConfigured
    partner = get_object_or_404(ReferralPartner, pk=partner_id)
    if not OrganisationMembership.objects.filter(organisation=partner.organisation, user=request.user,
                                                 role="owner", is_active=True).exists():
        return render(request, "dashboard/owner_forbidden.html", status=403)
    form = PayoutForm(request.POST)
    if form.is_valid():
        try:
            save_payout_details(partner, form.cleaned_data)
        except (ImproperlyConfigured, ValueError):
            messages.error(request, "Secure payout storage is unavailable. Please contact support.")
        else:
            AuditEvent.objects.create(actor=request.user, action="affiliate.payout_details_updated",
                                      target_type="ReferralPartner", target_id=str(partner.pk),
                                      summary="Encrypted payout details updated.")
            messages.success(request, "Payout details saved securely.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    response = redirect("partner_dashboard")
    response["Cache-Control"] = "no-store"
    return response


@login_required(login_url="login")
def affiliate_payout_review(request, partner_id):
    import json
    from .payouts import payout_cipher
    if not (request.user.is_superuser or request.user.has_perm("growth.approve_commission")):
        return render(request, "dashboard/owner_forbidden.html", status=403)
    partner = get_object_or_404(ReferralPartner, pk=partner_id)
    details = None
    if hasattr(partner, "payout_details"):
        details = json.loads(payout_cipher().decrypt(partner.payout_details.encrypted_details.encode()))
    AuditEvent.objects.create(actor=request.user, action="affiliate.payout_details_viewed",
        target_type="ReferralPartner", target_id=str(partner.pk), summary="Authorised payout staff reviewed bank details.")
    response = render(request, "growth/payout_review.html", {"partner": partner, "details": details})
    response["Cache-Control"] = "no-store"
    return response
