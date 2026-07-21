from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.utils import timezone
from accounts.models import UserProfile
from ats.models import ApplicationReminder, ATSResult, CV, EnterpriseBatch, EnterpriseCandidateResult, GeneratedCV, JobRole
from payments.models import Invoice, PaymentTransaction, Refund
from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan
from subscriptions.services import get_entitlements


def owner_required(user):
    return user.is_authenticated and user.is_superuser


@login_required(login_url='login')
def dashboard(request):
    """Compose the authorised dashboard from records owned by the login user.

    The effective plan comes from a non-expired active CustomerSubscription;
    otherwise access falls back to Free. Related CV, result, job, reminder and
    batch queries are filtered by ``request.user`` to prevent cross-account
    disclosure. Website-owner controls live separately at ``/owner/``.
    """
    user_profile, _created = UserProfile.objects.get_or_create(user=request.user)
    user_profile.reset_daily_usage_if_needed()
    recent_results = list(ATSResult.objects.filter(user=request.user).select_related('cv')[:5])
    uploaded_cvs = list(CV.objects.filter(user=request.user)[:5])
    saved_jobs = JobRole.objects.filter(user=request.user).annotate(result_count=Count('results'))[:5]
    reminders = ApplicationReminder.objects.filter(user=request.user, is_sent=False).select_related('job_role')[:5]
    generated_cvs = GeneratedCV.objects.filter(user=request.user).select_related('ats_result')[:5]
    enterprise_batches = EnterpriseBatch.objects.filter(user=request.user).select_related('job_role').annotate(candidate_count=Count('candidate_results'))[:5]
    entitlements = get_entitlements(request.user)
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

    now = timezone.now()
    month_start = now - timedelta(days=30)
    paid_transactions = PaymentTransaction.objects.filter(status="paid")
    revenue_total = paid_transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    revenue_30_days = paid_transactions.filter(created_at__gte=month_start).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    refunds_total = Refund.objects.exclude(status="rejected").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    users_total = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    free_users = UserProfile.objects.filter(plan="free").count()
    plus_users = UserProfile.objects.filter(plan__in=["plus", "professional"]).count()
    enterprise_users = UserProfile.objects.filter(plan="enterprise").count()
    payment_count = PaymentTransaction.objects.count()
    paid_count = paid_transactions.count()
    payment_success_rate = int((paid_count / payment_count) * 100) if payment_count else 0

    management_cards = [
        {
            "title": "Users",
            "value": users_total,
            "text": "Add, deactivate, delete, or change staff/superuser access.",
            "primary_label": "Manage users",
            "primary_url": "admin:auth_user_changelist",
            "secondary_label": "Add user",
            "secondary_url": "admin:auth_user_add",
        },
        {
            "title": "Subscriptions",
            "value": CustomerSubscription.objects.filter(status="active").count(),
            "text": "Change plan status, cancel subscriptions, and review renewal dates.",
            "primary_label": "Manage subscriptions",
            "primary_url": "admin:subscriptions_customersubscription_changelist",
            "secondary_label": "Plans",
            "secondary_url": "admin:subscriptions_subscriptionplan_changelist",
        },
        {
            "title": "Promo codes",
            "value": DiscountCode.objects.filter(is_active=True).count(),
            "text": "Create launch discounts, deactivate expired offers, and track redemptions.",
            "primary_label": "Manage codes",
            "primary_url": "admin:subscriptions_discountcode_changelist",
            "secondary_label": "Add code",
            "secondary_url": "admin:subscriptions_discountcode_add",
        },
        {
            "title": "Payments",
            "value": payment_count,
            "text": "Check checkout references, payment status, receipts, and provider IDs.",
            "primary_label": "Transactions",
            "primary_url": "admin:payments_paymenttransaction_changelist",
            "secondary_label": "Invoices",
            "secondary_url": "admin:payments_invoice_changelist",
        },
        {
            "title": "Refunds",
            "value": Refund.objects.count(),
            "text": "Record refund requests and approve, process, or reject them.",
            "primary_label": "Manage refunds",
            "primary_url": "admin:payments_refund_changelist",
            "secondary_label": "Add refund",
            "secondary_url": "admin:payments_refund_add",
        },
        {
            "title": "Reports",
            "value": ATSResult.objects.count(),
            "text": "Review ATS results, generated CVs, cover letters, and enterprise reports.",
            "primary_label": "Explore reports",
            "primary_url": "owner_reports",
            "secondary_label": "Enterprise",
            "secondary_url": "admin:ats_enterprisebatch_changelist",
        },
        {
            "title": "Website health",
            "value": payment_success_rate,
            "suffix": "%",
            "text": "Check operational health, revenue, assumptions, usage, and risks.",
            "primary_label": "Open health",
            "primary_url": "website_health",
            "secondary_label": "Financial inputs",
            "secondary_url": "admin:analytics_financialassumption_changelist",
        },
    ]

    context = {
        "summary": {
            "users_total": users_total,
            "active_users": active_users,
            "free_users": free_users,
            "plus_users": plus_users,
            "enterprise_users": enterprise_users,
            "revenue_total": revenue_total,
            "revenue_30_days": revenue_30_days,
            "refunds_total": refunds_total,
            "payment_success_rate": payment_success_rate,
            "open_invoices": Invoice.objects.filter(status="open").count(),
        },
        "management_cards": management_cards,
        "recent_users": User.objects.order_by("-date_joined")[:6],
        "recent_payments": PaymentTransaction.objects.select_related("user", "plan")[:6],
        "recent_refunds": Refund.objects.select_related("transaction", "transaction__user")[:6],
    }
    return render(request, "dashboard/owner_console.html", context)


@login_required(login_url='login')
def owner_reports(request):
    """Owner-only report explorer, separate from customer Enterprise tools."""
    if not request.user.is_superuser:
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
