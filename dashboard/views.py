from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from accounts.models import SocialAuthProvider, UserProfile
from ats.models import ApplicationReminder, ATSResult, CV, EnterpriseBatch, GeneratedCV, JobRole
from payments.models import Invoice, PaymentTransaction, Refund
from subscriptions.models import CustomerSubscription, SubscriptionPlan


@login_required(login_url='login')
def dashboard(request):
    """User dashboard showing uploaded CVs and recent ATS analyses."""
    user_profile, _created = UserProfile.objects.get_or_create(user=request.user)
    recent_results = ATSResult.objects.filter(user=request.user).select_related('cv')[:5]
    uploaded_cvs = CV.objects.filter(user=request.user)[:5]
    saved_jobs = JobRole.objects.filter(user=request.user)[:5]
    reminders = ApplicationReminder.objects.filter(user=request.user, is_sent=False).select_related('job_role')[:5]
    generated_cvs = GeneratedCV.objects.filter(user=request.user)[:5]
    enterprise_batches = EnterpriseBatch.objects.filter(user=request.user)[:5]
    is_owner = request.user.is_superuser
    social_providers = SocialAuthProvider.objects.all() if is_owner else SocialAuthProvider.objects.none()
    admin_stats = {}
    if is_owner:
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

    limit = user_profile.get_analysis_limit()
    usage_percent = 0
    if limit:
        usage_percent = min(100, int((user_profile.analyses_today / limit) * 100))

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
        'is_enterprise': is_owner or user_profile.plan == 'enterprise',
        'dashboard_scope': 'owner' if is_owner else user_profile.plan,
        'show_demo_preview': not uploaded_cvs.exists() and not recent_results.exists(),
        'demo_metrics': {
            'skills': 78,
            'keywords': 72,
            'experience': 86,
            'format': 90,
            'total': 82,
        },
        'plan': user_profile.plan,
        'analyses_today': user_profile.analyses_today,
        'limit': limit,
        'usage_percent': usage_percent,
    }

    return render(request, 'dashboard/home.html', context)
