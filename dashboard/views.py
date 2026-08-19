from datetime import date
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from accounts.models import UserProfile
from ats.models import ApplicationReminder, ATSResult, CV, EnterpriseBatch, EnterpriseCandidateResult, GeneratedCV, JobRole
from subscriptions.services import get_entitlements
from core.models import ExperienceFeedback
from governance.models import AuditEvent, ManagementAssignment, Organisation
from growth.models import (
    BulkPurchase, CommissionEntry, ConsentRecord, MarketingCampaign,
    PartnerProfile, ProviderConnection, ReferralPartner,
)


def owner_required(user):
    return user.is_authenticated and user.is_superuser


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def owner_governance_unlock(request):
    if not request.user.is_superuser:
        return render(request, "dashboard/owner_forbidden.html", status=403)
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("owner_console")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse("owner_console")
    if request.method == "POST":
        if request.user.check_password(request.POST.get("password", "")):
            request.session["owner_governance_verified_at"] = timezone.now().timestamp()
            AuditEvent.objects.create(
                actor=request.user, action="owner.governance_unlocked",
                summary="Owner completed password re-verification for governance access.",
            )
            return redirect(next_url)
        AuditEvent.objects.create(
            actor=request.user, action="owner.governance_unlock_failed",
            summary="Owner password re-verification failed.",
        )
        return render(request, "dashboard/owner_governance_unlock.html", {"next": next_url, "error": True}, status=403)
    return render(request, "dashboard/owner_governance_unlock.html", {"next": next_url})


MANAGEMENT_PERMISSIONS = {
    "partnerships": "growth.view_partnerprofile",
    "bulk_access": "growth.view_bulkpurchase",
    "marketing": "growth.view_marketingcampaign",
    "approvals": "growth.approve_campaign",
    "finance": "growth.view_commissionentry",
    "privacy": "growth.view_consentrecord",
    "integrations": "growth.view_providerconnection",
    "analytics": "growth.view_analyticsevent",
    "recruitment_reports": "ats.view_atsresult",
    "customer_experience": "core.view_experiencefeedback",
}


@login_required(login_url="login")
def management_dashboard(request):
    """Permission-aware operational workspace; never grants owner governance."""
    if request.user.is_superuser:
        return redirect("owner_console")
    if not request.user.is_staff or not any(request.user.has_perm(code) for code in MANAGEMENT_PERMISSIONS.values()):
        return render(request, "dashboard/owner_forbidden.html", status=403)

    definitions = [
        ("partnerships", "Partners", PartnerProfile.objects.count(), "Manage the partnership pipeline and assigned organisations.", "admin:growth_partnerprofile_changelist"),
        ("bulk_access", "Bulk access", BulkPurchase.objects.count(), "Manage institutional purchases, allocations and vouchers.", "admin:growth_bulkpurchase_changelist"),
        ("marketing", "Campaigns", MarketingCampaign.objects.count(), "Prepare channel-specific campaigns for review.", "admin:growth_marketingcampaign_changelist"),
        ("approvals", "Campaign approvals", MarketingCampaign.objects.filter(status="review").count(), "Review campaigns before publishing or expenditure.", "admin:growth_campaignapproval_changelist"),
        ("finance", "Partner commissions", CommissionEntry.objects.filter(status__in=["pending", "approved", "payable"]).count(), "Review commission liabilities and payment status.", "admin:growth_commissionentry_changelist"),
        ("privacy", "Consent records", ConsentRecord.objects.count(), "Review consent evidence, scope and withdrawal status.", "admin:growth_consentrecord_changelist"),
        ("integrations", "Provider connections", ProviderConnection.objects.count(), "Review non-secret provider connection status.", "admin:growth_providerconnection_changelist"),
        ("analytics", "Growth analytics", ReferralPartner.objects.filter(is_active=True).count(), "Review referral, campaign and conversion data.", "admin:growth_analyticsevent_changelist"),
        ("recruitment_reports", "Recruitment reports", ATSResult.objects.count(), "Review ATS and enterprise screening activity without changing customer records.", "management_reports"),
        ("customer_experience", "Customer feedback", ExperienceFeedback.objects.count(), "Review ratings, comments and experience trends.", "management_feedback"),
    ]
    cards = [
        {"title": title, "value": value, "text": text, "url": url}
        for key, title, value, text, url in definitions
        if request.user.has_perm(MANAGEMENT_PERMISSIONS[key])
    ]
    return render(request, "dashboard/management_home.html", {"management_cards": cards})


def enterprise_dashboard(request, user_profile, entitlements):
    candidates = EnterpriseCandidateResult.objects.filter(batch__user=request.user)
    batches = EnterpriseBatch.objects.filter(user=request.user).select_related("job_role").annotate(
        candidate_count=Count("candidate_results"),
        qualified_count=Count("candidate_results", filter=Q(candidate_results__score__gte=55)),
        mandatory_pass_count=Count("candidate_results", filter=Q(candidate_results__mandatory_pass=True)),
        shortlisted_count=Count("candidate_results", filter=Q(candidate_results__review_status="shortlisted")),
        pending_count=Count("candidate_results", filter=Q(candidate_results__review_status="pending")),
    )
    total = candidates.count()
    qualified = candidates.filter(score__gte=55).count()
    mandatory_pass = candidates.filter(mandatory_pass=True).count()
    shortlisted = candidates.filter(review_status="shortlisted").count()
    awaiting_email = candidates.exclude(review_status="pending").filter(email_sent_at__isnull=True).count()
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage_count = candidates.filter(created_at__gte=month_start).count()
    limit = entitlements.bulk_limit
    return render(request, "dashboard/enterprise_home.html", {
        "batches": batches[:20],
        "summary": {
            "jobs": batches.count(), "applicants": total, "qualified": qualified,
            "below_threshold": total - qualified, "mandatory_pass": mandatory_pass,
            "mandatory_failed": total - mandatory_pass, "shortlisted": shortlisted,
            "awaiting_email": awaiting_email,
        },
        "usage_count": usage_count, "limit": limit,
        "usage_percent": min(100, int((usage_count / limit) * 100)) if limit else 0,
        "remaining_usage": max(0, limit - usage_count), "user_profile": user_profile,
    })


@login_required(login_url='login')
def dashboard(request):
    """Compose the authorised dashboard from records owned by the login user.

    The effective plan comes from a non-expired active CustomerSubscription;
    otherwise access falls back to Free. Related CV, result, job, reminder and
    batch queries are filtered by ``request.user`` to prevent cross-account
    disclosure. Website-owner controls live separately at ``/owner/``.
    """
    if request.user.is_superuser:
        return redirect("owner_console")
    if request.user.is_staff:
        return redirect("management_dashboard")

    user_profile, _created = UserProfile.objects.get_or_create(user=request.user)
    user_profile.reset_daily_usage_if_needed()
    entitlements = get_entitlements(request.user)
    if entitlements.code == "enterprise":
        return enterprise_dashboard(request, user_profile, entitlements)

    recent_results = list(ATSResult.objects.filter(user=request.user).select_related('cv')[:5])
    uploaded_cvs = list(CV.objects.filter(user=request.user)[:5])
    saved_jobs = JobRole.objects.filter(user=request.user).annotate(result_count=Count('results'))[:5]
    reminders = ApplicationReminder.objects.filter(user=request.user, is_sent=False).select_related('job_role')[:5]
    generated_cvs = GeneratedCV.objects.filter(user=request.user).select_related('ats_result')[:5]
    enterprise_batches = EnterpriseBatch.objects.filter(user=request.user).select_related('job_role').annotate(candidate_count=Count('candidate_results'))[:5]
    active_subscription = entitlements.subscription
    effective_plan = entitlements.code

    is_enterprise = effective_plan == 'enterprise'

    limit = entitlements.bulk_limit if is_enterprise else entitlements.analysis_limit
    usage_label = 'CV scans this month' if is_enterprise else 'Validations this month'
    if is_enterprise:
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage_count = EnterpriseCandidateResult.objects.filter(
            batch__user=request.user,
            created_at__gte=month_start,
        ).count()
    else:
        usage_count = user_profile.analyses_this_month
    usage_percent = 0
    if limit:
        usage_percent = min(100, int((usage_count / limit) * 100))
    remaining_usage = max(0, limit - usage_count)
    if remaining_usage == 0:
        usage_alert_level = 'danger'
        usage_alert = f'Monthly limit reached: {usage_count} of {limit} {usage_label.lower()}. Your allowance renews on the date shown below.'
    elif usage_percent >= 80:
        usage_alert_level = 'warning'
        usage_alert = f'You are close to your monthly limit. {remaining_usage} of {limit} uses remain.'
    else:
        usage_alert_level = 'info'
        usage_alert = f'{remaining_usage} of {limit} monthly uses remain on your {effective_plan.title()} plan.'

    today = timezone.localdate()
    next_month = date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1)
    subscription_started = active_subscription.started_at if active_subscription else user_profile.created_at
    next_renewal = active_subscription.current_period_end if active_subscription and active_subscription.current_period_end else next_month
    renewal_label = 'Next payment renewal' if active_subscription and active_subscription.plan.price > 0 else 'Allowance renews'

    service_features = {
        'free': [
            '5 CV-to-job validations each month',
            '1 CV stored securely for up to 30 days',
            'ATS compatibility and match recommendations',
        ],
        'plus': [
            '20 CV-to-job validations each month',
            'Tailored CV rewrite for each tested role',
            'Tailored cover letter for each tested role',
        ],
        'professional': [
            '20 CV-to-job validations each month',
            'Tailored CV rewrites and cover letters',
            'Full ATS compatibility results',
        ],
        'enterprise': [
            'Bulk screening for up to 50 CVs each month',
            'Dedicated candidate ranking reports',
            'No CV rewriting or cover-letter generation',
        ],
    }.get(effective_plan, [])

    context = {
        'user_profile': user_profile,
        'recent_results': recent_results,
        'uploaded_cvs': uploaded_cvs,
        'saved_jobs': saved_jobs,
        'reminders': reminders,
        'generated_cvs': generated_cvs,
        'enterprise_batches': enterprise_batches,
        'is_owner': request.user.is_superuser,
        'is_enterprise': is_enterprise,
        'dashboard_scope': effective_plan,
        'show_demo_preview': not uploaded_cvs and not recent_results,
        'demo_metrics': {
            'skills': 78,
            'keywords': 72,
            'experience': 86,
            'format': 90,
            'total': 82,
        },
        'plan': effective_plan,
        'usage_count': usage_count,
        'usage_label': usage_label,
        'limit': limit,
        'usage_percent': usage_percent,
        'remaining_usage': remaining_usage,
        'usage_alert': usage_alert,
        'usage_alert_level': usage_alert_level,
        'subscription_started': subscription_started,
        'next_renewal': next_renewal,
        'renewal_label': renewal_label,
        'subscription_status': active_subscription.status if active_subscription else 'active',
        'service_features': service_features,
    }

    return render(request, 'dashboard/home.html', context)


@login_required(login_url='login')
def owner_console(request):
    if not request.user.is_superuser:
        return render(request, "dashboard/owner_forbidden.html", status=403)
    management_cards = [
        {
            "title": "Management roles",
            "value": ManagementAssignment.objects.filter(is_active=True).count(),
            "text": "Assign specialist roles without granting platform-owner access.",
            "primary_label": "Manage roles",
            "primary_url": "admin:governance_managementassignment_changelist",
            "secondary_label": "Role groups",
            "secondary_url": "admin:auth_group_changelist",
        },
        {
            "title": "Organisations",
            "value": Organisation.objects.count(),
            "text": "Govern enterprise customers, universities, agencies and institutional partners.",
            "primary_label": "Manage organisations",
            "primary_url": "admin:governance_organisation_changelist",
            "secondary_label": "Memberships",
            "secondary_url": "admin:governance_organisationmembership_changelist",
        },
        {
            "title": "Provider governance",
            "value": ProviderConnection.objects.count(),
            "text": "Supervise non-secret setup status for Google, LinkedIn, Meta, TikTok and analytics.",
            "primary_label": "Provider settings",
            "primary_url": "admin:growth_providerconnection_changelist",
            "secondary_label": "Consent records",
            "secondary_url": "admin:growth_consentrecord_changelist",
        },
        {
            "title": "Governance audit",
            "value": AuditEvent.objects.count(),
            "text": "Review security-sensitive management and permission activity.",
            "primary_label": "Open audit",
            "primary_url": "admin:governance_auditevent_changelist",
            "secondary_label": "Provider status",
            "secondary_url": "admin:growth_providerconnection_changelist",
        },
        {
            "title": "Platform health",
            "value": "Live",
            "text": "Supervise technical, data-quality, usage and financial health with test accounts excluded from KPIs.",
            "primary_label": "Open health",
            "primary_url": "website_health",
            "secondary_label": "Financial assumptions",
            "secondary_url": "admin:analytics_financialassumption_changelist",
        },
    ]

    context = {
        "summary": {
            "active_managers": ManagementAssignment.objects.filter(is_active=True).count(),
            "organisations": Organisation.objects.count(),
            "active_partners": PartnerProfile.objects.filter(stage="active").count(),
            "providers_ready": ProviderConnection.objects.filter(status="connected").count(),
        },
        "management_cards": management_cards,
    }
    return render(request, "dashboard/owner_console.html", context)


@login_required(login_url='login')
def management_reports(request):
    """Read-only recruitment reporting for authorised managers and owners."""
    if not (request.user.is_superuser or request.user.has_perm("ats.view_atsresult")):
        return render(request, "dashboard/owner_forbidden.html", status=403)

    query = request.GET.get("q", "").strip()
    results = ATSResult.objects.select_related("user", "cv").order_by("-created_at")
    batches = EnterpriseBatch.objects.select_related("user", "job_role").order_by("-created_at")
    if query:
        results = results.filter(
            Q(user__username__icontains=query) | Q(user__email__icontains=query)
            | Q(job_title__icontains=query) | Q(cv__title__icontains=query)
        )
        batches = batches.filter(
            Q(user__username__icontains=query) | Q(user__email__icontains=query)
            | Q(title__icontains=query) | Q(job_role__title__icontains=query)
        )

    return render(request, "dashboard/owner_reports.html", {
        "query": query,
        "results": results[:100],
        "batches": batches[:100],
        "result_count": results.count(),
        "batch_count": batches.count(),
    })


@login_required(login_url="login")
def management_feedback(request):
    """Read-only experience feedback for authorised managers and owners."""
    if not (request.user.is_superuser or request.user.has_perm("core.view_experiencefeedback")):
        return render(request, "dashboard/owner_forbidden.html", status=403)

    feedback = ExperienceFeedback.objects.select_related("user")
    feature = request.GET.get("feature", "").strip()
    if feature in dict(ExperienceFeedback.FEATURE_CHOICES):
        feedback = feedback.filter(feature=feature)
    summary = feedback.aggregate(
        count=Count("id"),
        average=Avg("rating"),
    )
    distribution = {
        row["rating"]: row["count"]
        for row in feedback.values("rating").annotate(count=Count("id"))
    }
    return render(request, "dashboard/owner_feedback.html", {
        "feedback": feedback[:100],
        "selected_feature": feature,
        "feature_choices": ExperienceFeedback.FEATURE_CHOICES,
        "summary": {
            "count": summary["count"] or 0,
            "average": round(summary["average"] or 0, 1),
            "pending_testimonials": feedback.filter(moderation_status="pending").count(),
            "positive": feedback.filter(rating__gte=4).count(),
        },
        "distribution": distribution,
    })
