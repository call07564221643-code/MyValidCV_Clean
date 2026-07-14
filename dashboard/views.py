from datetime import date

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from accounts.models import SocialAuthProvider, UserProfile
from ats.models import ApplicationReminder, ATSResult, CV, EnterpriseBatch, EnterpriseCandidateResult, GeneratedCV, JobRole
from payments.models import Invoice, PaymentTransaction, Refund
from subscriptions.models import CustomerSubscription, SubscriptionPlan


@login_required(login_url='login')
def dashboard(request):
    """User dashboard showing uploaded CVs and recent ATS analyses."""
    user_profile, _created = UserProfile.objects.get_or_create(user=request.user)
    user_profile.reset_daily_usage_if_needed()
    recent_results = list(ATSResult.objects.filter(user=request.user).select_related('cv')[:5])
    uploaded_cvs = list(CV.objects.filter(user=request.user)[:5])
    saved_jobs = JobRole.objects.filter(user=request.user).annotate(result_count=Count('results'))[:5]
    reminders = ApplicationReminder.objects.filter(user=request.user, is_sent=False).select_related('job_role')[:5]
    generated_cvs = GeneratedCV.objects.filter(user=request.user).select_related('ats_result')[:5]
    enterprise_batches = EnterpriseBatch.objects.filter(user=request.user).select_related('job_role').annotate(candidate_count=Count('candidate_results'))[:5]
    is_owner = request.user.is_superuser
    active_subscription = CustomerSubscription.objects.filter(
        user=request.user,
        status='active',
    ).select_related('plan').first()
    if active_subscription and active_subscription.current_period_end and active_subscription.current_period_end <= timezone.now():
        active_subscription = None

    paid_plan_code = active_subscription.plan.code if active_subscription else None
    if is_owner:
        effective_plan = 'enterprise'
    elif paid_plan_code in ('plus', 'professional', 'enterprise'):
        effective_plan = paid_plan_code
    else:
        effective_plan = 'free'

    is_enterprise = is_owner or effective_plan == 'enterprise'
    social_providers = SocialAuthProvider.objects.all() if is_owner else SocialAuthProvider.objects.none()
    admin_stats = {}
    if is_owner:
        admin_stats = cache.get('owner-dashboard-stats')
        if admin_stats is None:
            admin_stats = {
            'users': UserProfile.objects.count(),
            'active_subscriptions': CustomerSubscription.objects.filter(status='active').count(),
            'payments': PaymentTransaction.objects.count(),
            'open_invoices': Invoice.objects.filter(status='open').count(),
            'refunds': Refund.objects.count(),
            'plans': SubscriptionPlan.objects.filter(is_active=True).count(),
            'ats_results': ATSResult.objects.count(),
            'enterprise_batches': EnterpriseBatch.objects.count(),
            }
            cache.set('owner-dashboard-stats', admin_stats, 60)

    plan_limits = {'free': 5, 'plus': 20, 'professional': 20, 'enterprise': 50}
    if active_subscription and effective_plan == 'enterprise':
        limit = active_subscription.plan.monthly_bulk_cv_limit or 50
    elif active_subscription:
        limit = active_subscription.plan.daily_analysis_limit
    else:
        free_plan = SubscriptionPlan.objects.filter(code='free', is_active=True).first()
        limit = free_plan.daily_analysis_limit if free_plan else plan_limits.get(effective_plan, 5)
    usage_label = 'CV scans this month' if is_enterprise else 'Validations this month'
    if is_enterprise and not is_owner:
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage_count = EnterpriseCandidateResult.objects.filter(
            batch__user=request.user,
            created_at__gte=month_start,
        ).count()
    else:
        usage_count = user_profile.analyses_today
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
        'social_providers': social_providers,
        'admin_stats': admin_stats,
        'is_owner': is_owner,
        'is_enterprise': is_enterprise,
        'dashboard_scope': 'owner' if is_owner else effective_plan,
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
