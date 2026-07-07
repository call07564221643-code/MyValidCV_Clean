from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Analysis


@login_required(login_url='login')
def dashboard(request):
    """User dashboard showing usage and recent analyses."""
    user_profile = request.user.profile
    recent_analyses = Analysis.objects.filter(user=request.user)[:5]

    context = {
        'user_profile': user_profile,
        'recent_analyses': recent_analyses,
        'plan': user_profile.plan,
        'analyses_today': user_profile.analyses_today,
        'limit': user_profile.get_analysis_limit(),
    }

    return render(request, 'dashboard/home.html', context)
